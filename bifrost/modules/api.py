"""Read-only v1 views of what only Bifrost holds: tables, page notes, the Codes ledger, collections, links"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from . import faces, photo_collections, tables


class NotFound(Exception):
    pass


def col_no(grid: dict, i: int) -> int:
    return grid["cols"][i].get("no") or i + 1


def prefix(pid: str, page: int) -> str:
    """'69T5AU' on page 1, '69T5AU.P2' after it; '' without a PID"""
    return pid + (f".P{page}" if page > 1 else "") if pid else ""


def handles(grid: dict, rows=None, cols=None) -> list[str]:
    """Gramps handles linked in the given rows and columns (all by default)"""
    rids = None if rows is None else {grid["rows"][j]["id"] for j in rows}
    cids = None if cols is None else {grid["cols"][i]["id"] for i in cols}
    found = (h for rid, row in (grid.get("people") or {}).items() if rids is None or rid in rids
             for cid, h in row.items() if cids is None or cid in cids)
    return list(dict.fromkeys(found))


def _person(handle: str, people: dict) -> dict:
    found = people.get(handle)
    if not found:
        return {"handle": handle}
    if found.get("missing"):
        return {"handle": handle, "missing": True}
    return {"handle": handle, "gramps_id": found["gramps_id"], "name": found["name"]}


def _cells(grid: dict, j: int, cols, people: dict) -> list[dict]:
    rid = grid["rows"][j]["id"]
    vals = grid["cells"].get(rid, {})
    trans = (grid.get("trans") or {}).get(rid, {})
    linked = (grid.get("people") or {}).get(rid, {})
    out = []
    for i in cols:
        col = grid["cols"][i]
        cid = col["id"]
        if cid in vals or cid in trans or cid in linked:
            out.append({"column": col_no(grid, i), "name": col["name"], "value": vals.get(cid, ""),
                        "translation": trans.get(cid),
                        "person": _person(linked[cid], people) if cid in linked else None})
    return out


def _line(grid: dict, j: int, cols, people: dict, pin_prefix: str, col: int | None = None) -> dict:
    no = grid["first_line"] + j
    pin = f"{pin_prefix}.L{no}" + (f".C{col}" if col else "") if pin_prefix else None
    return {"line": no, "pinpoint": pin, "cells": _cells(grid, j, cols, people)}


def column(grid: dict, i: int) -> dict:
    col = grid["cols"][i]
    return {"no": col_no(grid, i), "name": col["name"], "translation": col.get("trans") or None,
            "person_column": bool(col.get("person")), "household": col["id"] == grid.get("group_col")}


def table(grid: dict, people: dict, pin_prefix: str) -> dict:
    """Every line and column of a grid, with its layout in page fractions"""
    cols = range(len(grid["cols"]))
    return {
        "first_line": grid["first_line"],
        "columns": [column(grid, i) for i in cols],
        "lines": [_line(grid, j, cols, people, pin_prefix) for j in range(len(grid["rows"]))],
        "layout": {"frame": grid["frame"], "columns": [c["u"] for c in grid["cols"]],
                   "lines": [r["v"] for r in grid["rows"]]},
    }


def select(grid: dict, pin: dict) -> tuple[list[int], list[int]]:
    """The row and column indexes a pinpoint covers, or NotFound"""
    n, first = len(grid["rows"]), grid["first_line"]
    rows = list(range(n))
    if pin["line"] is not None:
        wanted = range(pin["line"], pin["last"] + 1)
        missing = next((no for no in wanted if not 0 <= no - first < n), None)
        if missing is not None:
            raise NotFound(f"line {missing} isn't in the table on page {pin['page']}"
                           f" (lines {first}-{first + n - 1})")
        rows = [no - first for no in wanted]
    cols = list(range(len(grid["cols"])))
    if pin["col"] is not None:
        cols = [i for i in cols if col_no(grid, i) == pin["col"]][:1]
        if not cols:
            raise NotFound(f"column {pin['col']} isn't in the table on page {pin['page']}")
    return rows, cols


def region(grid: dict, rows: list[int], cols: list[int]) -> dict:
    """The covered cells' outline (TL, TR, BR, BL) and bounding box, in page fractions"""
    pts = tables.grid_points(grid)
    top, bottom, left, right = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    corners = [pts[top][left], pts[top][right], pts[bottom][right], pts[bottom][left]]
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    return {"box": [round(v, 4) for v in (min(xs), min(ys), max(xs), max(ys))],
            "corners": [[round(x, 4), round(y, 4)] for x, y in corners]}


def pinpoint(pin: dict, doc_id: int, title: str, grid: dict, rows: list[int], cols: list[int],
             people: dict) -> dict:
    pin_prefix = prefix(pin["code"], pin["page"])
    frag = tables.pinpoint_fragment(pin)
    return {
        "pinpoint": pin_prefix + (f".{frag}" if frag else ""),
        "pid": pin["code"],
        "paperless_id": doc_id,
        "title": title,
        "page": pin["page"],
        "column": column(grid, cols[0]) if pin["col"] is not None else None,
        "lines": [_line(grid, j, cols, people, pin_prefix, pin["col"]) for j in rows],
        "region": region(grid, rows, cols),
    }


def doc_ids(conn: sqlite3.Connection) -> list[int]:
    return [r[0] for r in conn.execute(
        "SELECT paperless_id FROM doc_tables UNION SELECT paperless_id FROM page_notes ORDER BY 1")]


def doc_title(conn: sqlite3.Connection, doc_id: int) -> str:
    row = conn.execute(
        "SELECT MAX(title) FROM (SELECT title FROM doc_tables WHERE paperless_id=?"
        " UNION ALL SELECT title FROM page_notes WHERE paperless_id=?)", (doc_id, doc_id)).fetchone()
    return row[0] or ""


def grids(conn: sqlite3.Connection, doc_id: int) -> dict[int, dict]:
    return {r["page"]: json.loads(r["grid"]) for r in conn.execute(
        "SELECT page, grid FROM doc_tables WHERE paperless_id=? ORDER BY page", (doc_id,))}


def document(conn: sqlite3.Connection, doc_id: int, pid: str, people: dict) -> dict:
    """A document's tables and notes, page by page"""
    by_page = grids(conn, doc_id)
    notes: dict[int, list[dict]] = {}
    for r in conn.execute("SELECT * FROM page_notes WHERE paperless_id=? ORDER BY page, id", (doc_id,)):
        notes.setdefault(r["page"], []).append(
            {k: r[k] for k in ("x", "y", "text", "created_at", "updated_at")})
    pages = []
    for page in sorted(set(by_page) | set(notes)):
        grid = by_page.get(page)
        pages.append({"page": page, "table": table(grid, people, prefix(pid, page)) if grid else None,
                      "notes": notes.get(page, [])})
    return {"pid": pid or None, "paperless_id": doc_id, "title": doc_title(conn, doc_id),
            "translations": tables.doc_options(conn, doc_id)["translations"], "pages": pages}


def children(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in conn.execute("SELECT object_id, parent_id FROM objects WHERE parent_id IS NOT NULL ORDER BY object_id"):
        out.setdefault(r["parent_id"], []).append(r["object_id"])
    return out


def known(row: dict) -> bool:
    return row["in_ledger"] or bool(row["paperless"])


def code(row: dict, kids: dict[str, list[str]]) -> dict:
    """A Codes ledger entry without the Codes page's own flags"""
    gone = row["withdrawn"]
    return {
        "code": row["code"], "status": row["status"], "type": row["type"], "kind": row["kind"],
        "description": row["note"], "notes": row["notes"] or None, "title": row["title"],
        "parent": row["parent"], "location": row["location"], "children": kids.get(row["code"], []),
        "created": row["created"], "minted": row["minted"],
        "pencilings": [{"at": p["at"], "crossed": p["crossed"]} for p in row["pencilings"]],
        "withdrawn": {"at": gone, "reason": row["withdrawn_reason"], "successor": row["successor"]}
        if gone else None,
        "predecessors": row["predecessors"], "scans": row["scans"],
        "instances": [{"where": i["where"], "text": i["text"], "url": i["url"]} for i in row["instances"]],
        "history": row["history"],
    }


def collections(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for c in photo_collections.list_all(conn):
        slots = conn.execute("SELECT seq, asset_id, added_at FROM collection_items WHERE collection_id=?"
                             " ORDER BY seq", (c["id"],))
        out.append({k: c[k] for k in ("name", "description", "created_at", "updated_at")}
                   | {"slots": [{"slot": s["seq"], "asset_id": s["asset_id"], "added_at": s["added_at"]}
                                for s in slots]})
    return out


def citation_inputs(conn: sqlite3.Connection) -> dict:
    return {
        "sources": [{"source_handle": r["handle"], "record_type": r["record_type"],
                     "inputs": json.loads(r["inputs"]), "used_at": r["used_at"]}
                    for r in conn.execute("SELECT * FROM citation_sources ORDER BY used_at")],
        "citations": [{"citation_handle": r["citation_handle"], "record_type": r["record_type"],
                       "draft": json.loads(r["draft"]), "created_at": r["created_at"]}
                      for r in conn.execute("SELECT * FROM citation_drafts ORDER BY created_at")],
    }


def export(conn: sqlite3.Connection, pids: dict[int, str], code_rows: list[dict]) -> dict:
    """Everything only Bifrost holds, people as bare Gramps handles"""
    kids = children(conn)
    return {
        "api": "v1",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "documents": [document(conn, d, pids.get(d, ""), {}) for d in doc_ids(conn)],
        "codes": [code(r, kids) for r in code_rows if known(r)],
        "collections": collections(conn),
        "person_links": faces.list_links(conn),
        "citation_inputs": citation_inputs(conn),
    }

