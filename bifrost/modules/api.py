"""Read-only v1 views of what only Bifrost holds: the Codes ledger, collections, photo links"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from . import photo_collections


def known(row: dict) -> bool:
    return row["in_ledger"] or bool(row["paperless"])


def code(row: dict) -> dict:
    """A Codes ledger entry without the Codes page's own flags"""
    gone = row["withdrawn"]
    return {
        "code": row["code"], "status": row["status"], "type": row["type"], "title": row["title"],
        "created": row["created"], "minted": row["minted"],
        "withdrawn": {"at": gone, "reason": row["withdrawn_reason"], "superseded_by": row["superseded_by"]}
        if gone else None,
        "supersedes": row["supersedes"], "history": row["history"],
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


def photo_links(conn: sqlite3.Connection) -> list[dict]:
    """Every photo that has links, with them in the order they were added"""
    out: dict[str, list[dict]] = {}
    for r in conn.execute("SELECT asset_id, url, added_at FROM photo_links ORDER BY asset_id, id"):
        out.setdefault(r["asset_id"], []).append({"url": r["url"], "added_at": r["added_at"]})
    return [{"asset_id": a, "links": links} for a, links in out.items()]


def export(conn: sqlite3.Connection, code_rows: list[dict]) -> dict:
    """Everything only Bifrost holds"""
    return {
        "api": "v1",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "codes": [code(r) for r in code_rows if known(r)],
        "collections": collections(conn),
        "photo_links": photo_links(conn),
    }
