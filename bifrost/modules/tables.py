"""Table grids over Paperless document pages: layout, values, page images, Gemini transcription"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime, timezone

from ..core.clients import GeminiClient, GeminiError, PaperlessClient

MAX_COLS = 120
MAX_ROWS = 400
NAME_MAX = 200
VALUE_MAX = 2000
NOTE_MAX = 10000
LINE_LIMIT = 99999
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_GRAMPS_ID_RE = re.compile(r"^[A-Za-z]{0,2}\d+$")
_WORD_RE = re.compile(r"[^\W_]+(?:['-][^\W_]+)*")
_PINPOINT_RE = re.compile(
    r"^(?P<code>[A-Z0-9]{4,8})(?:\.P(?P<page>[1-9]\d*))?"
    r"(?:\.L(?P<line>\d+)(?:-(?P<last>\d+))?)?(?:\.C(?P<col>[1-9]\d*))?$")

RASTER_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff", "image/bmp"}
BROWSER_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
DEFAULT_DPI, MIN_DPI, MAX_DPI = 200, 100, 600
MAX_SIDE = 12000

BAND_ROWS = 8
CONCURRENCY = 3

TRANSCRIBE_PROMPT = """This image is a band cut from a table in a historical or \
genealogical document, such as a census schedule. Red lines outline the table's \
cells. Each row is labeled with its line number in the white margins at the left \
and right, and each column with a key in the white strip at the top.

The columns, by key:
{columns}

Transcribe every cell of {lines}, under the key of its column. Copy the text \
exactly as it appears: keep the original spelling, abbreviations, capitalization, \
punctuation and language, and keep ditto marks as written. Transcribe printed and \
handwritten text, numbers and marks such as check marks or dashes. A blank cell is \
an empty string. For a genuinely illegible word write [illegible]; for an uncertain \
reading write the best guess followed by a question mark in brackets, e.g. \
Andersson[?]."""


class GridError(ValueError):
    """A grid the API refuses"""


class Conflict(Exception):
    """The table changed since the client loaded it"""

    def __init__(self, rev: int) -> None:
        super().__init__(rev)
        self.rev = rev


class PageError(Exception):
    """A page Bifrost cannot show"""


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


# ---- grid

def _unit(value, what: str) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise GridError(f"{what} is not a number") from None
    if not math.isfinite(f):
        raise GridError(f"{what} is not a number")
    return min(1.0, max(0.0, f))


def _pair(value, what: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise GridError(f"{what} needs two numbers")
    return [_unit(value[0], what), _unit(value[1], what)]


def _lines(raw, key: str, limit: int, what: str, named: bool = False) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        raise GridError(f"a table needs at least one {what}")
    if len(raw) > limit:
        raise GridError(f"a table has at most {limit} {what}s")
    out: list[dict] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise GridError(f"{what} {i + 1} is not an object")
        lid = str(item.get("id") or "")
        if not _ID_RE.match(lid) or lid in seen:
            raise GridError(f"{what} {i + 1} has a missing or repeated id")
        seen.add(lid)
        pos = [0.0, 0.0] if i == 0 else _pair(item.get(key), f"{what} {i + 1}")
        if out and (pos[0] < out[-1][key][0] or pos[1] < out[-1][key][1]):
            raise GridError(f"the {what}s are out of order")
        line = {"id": lid}
        if named:
            line["name"] = " ".join(str(item.get("name") or "").split())[:NAME_MAX]
            line["trans"] = " ".join(str(item.get("trans") or "").split())[:NAME_MAX]
            if item.get("person") is True:
                line["person"] = True
            no = item.get("no")
            if isinstance(no, int) and not isinstance(no, bool) and 1 <= no <= 9999:
                line["no"] = no
        line[key] = pos
        out.append(line)
    return out


def _values(raw, row_ids: set[str], col_ids: set[str], what: str) -> dict[str, dict[str, str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise GridError(f"the {what} are not an object")
    out: dict[str, dict[str, str]] = {}
    for rid, vals in raw.items():
        if rid not in row_ids or not isinstance(vals, dict):
            continue
        row = {}
        for cid, val in vals.items():
            if cid not in col_ids or isinstance(val, bool) or not isinstance(val, (str, int, float)):
                continue
            text = str(val).strip()
            if len(text) > VALUE_MAX:
                raise GridError(f"a value is longer than {VALUE_MAX} characters")
            if text:
                row[cid] = text
        if row:
            out[rid] = row
    return out


def valid_handle(handle) -> bool:
    return isinstance(handle, str) and bool(_HANDLE_RE.match(handle))


def _links(raw, row_ids: set[str], col_ids: set[str]) -> dict[str, dict[str, str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise GridError("the person links are not an object")
    out: dict[str, dict[str, str]] = {}
    for rid, vals in raw.items():
        if rid in row_ids and isinstance(vals, dict):
            row = {cid: h for cid, h in vals.items() if cid in col_ids and valid_handle(h)}
            if row:
                out[rid] = row
    return out


def normalize_grid(raw) -> dict:
    """A clean copy of a client's grid, or GridError"""
    if not isinstance(raw, dict):
        raise GridError("the table is not an object")
    frame = raw.get("frame")
    if not isinstance(frame, list) or len(frame) != 4:
        raise GridError("the frame needs four corners")
    cols = _lines(raw.get("cols"), "u", MAX_COLS, "column", named=True)
    rows = _lines(raw.get("rows"), "v", MAX_ROWS, "row")
    try:
        first = int(raw.get("first_line", 1))
    except (TypeError, ValueError):
        raise GridError("the first line number is not a whole number") from None
    col_ids = {c["id"] for c in cols}
    row_ids = {r["id"] for r in rows}
    group = raw.get("group_col")
    return {
        "frame": [_pair(p, "a frame corner") for p in frame],
        "cols": cols,
        "rows": rows,
        "first_line": min(LINE_LIMIT, max(-LINE_LIMIT, first)),
        "group_col": group if group in col_ids else None,
        "cells": _values(raw.get("cells"), row_ids, col_ids, "cells"),
        "trans": _values(raw.get("trans"), row_ids, col_ids, "translations"),
        "people": _links(raw.get("people"), row_ids, col_ids),
    }


# ---- Gramps people linked to cells

def people_rules(query: str) -> dict | None:
    """Gramps filter rules for a name query: every word must be in one of the person's names"""
    words = _WORD_RE.findall(query)[:4]
    words = [w for w in words if len(w) > 1] or words[:1]
    if not words:
        return None
    if len(words) == 1 and _GRAMPS_ID_RE.match(words[0]):
        return {"function": "or", "rules": [{"name": "SearchName", "values": words},
                                            {"name": "RegExpIdOf", "values": words}]}
    return {"function": "and", "rules": [{"name": "SearchName", "values": [w]} for w in words]}


def person_summary(person: dict) -> dict:
    """Given name first, birth and death dates, and whether Gramps has a picture of them"""
    prof = person.get("profile") or {}
    parts = (prof.get(k, "").strip() for k in ("name_given", "name_surname", "name_suffix"))
    return {
        "handle": person["handle"], "gramps_id": person.get("gramps_id", ""),
        "name": " ".join(p for p in parts if p) or prof.get("name_display") or person.get("gramps_id", ""),
        "birth": (prof.get("birth") or {}).get("date", ""),
        "death": (prof.get("death") or {}).get("date", ""),
        "photo": bool(person.get("media_list")),
    }


def to_csv(grid: dict) -> str:
    """One column per table column, each followed by its translation when the table has any"""
    cols = grid["cols"]
    trans = grid.get("trans") or {}
    translated = bool(trans) or any(c.get("trans") for c in cols)
    head = ["Line"]
    for i, c in enumerate(cols):
        name = c["name"] or f"Column {i + 1}"
        head += [name, c.get("trans") or f"{name} (translation)"] if translated else [name]
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(head)
    for j, r in enumerate(grid["rows"]):
        vals = grid["cells"].get(r["id"], {})
        tvals = trans.get(r["id"], {})
        line = [grid["first_line"] + j]
        for c in cols:
            line += [vals.get(c["id"], ""), tvals.get(c["id"], "")] if translated else [vals.get(c["id"], "")]
        out.writerow(line)
    return buf.getvalue()


# ---- pinpoints: PID[.Pn].Ln[-m][.Cn]

def parse_pinpoint(text: str) -> dict | None:
    """'69t5au.p2.l1-5' -> {'code': '69T5AU', 'page': 2, 'line': 1, 'last': 5, 'col': None}"""
    m = _PINPOINT_RE.match(re.sub(r"\s+", "", text or "").upper())
    if not m:
        return None
    line = int(m["line"]) if m["line"] else None
    last = int(m["last"]) if m["last"] else line
    if line is not None and last < line:
        line, last = last, line
    return {"code": m["code"], "page": int(m["page"] or 1), "line": line, "last": last,
            "col": int(m["col"]) if m["col"] else None}


def pinpoint_fragment(pin: dict) -> str:
    """The viewer's #fragment for a pinpoint: 'L1-5.C6'"""
    parts = []
    if pin["line"] is not None:
        parts.append(f"L{pin['line']}" + (f"-{pin['last']}" if pin["last"] != pin["line"] else ""))
    if pin["col"] is not None:
        parts.append(f"C{pin['col']}")
    return ".".join(parts)


async def find_doc(paperless: PaperlessClient, conn: sqlite3.Connection,
                   field_id: int, code: str) -> int | None:
    """The Paperless document carrying the PID, or the one Bifrost minted it for"""
    if field_id:
        try:
            found = await paperless.documents_with_value(field_id, code)
        except Exception:  # noqa: BLE001
            found = []
        if found:
            return found[0]
    row = conn.execute("SELECT source_id FROM minted_media WHERE gramps_id=? AND source_system='paperless'",
                       (code,)).fetchone()
    return int(row["source_id"]) if row and str(row["source_id"]).isdigit() else None


# ---- geometry, in page fractions

def _lerp(a, b, t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _meet(s1, s2) -> tuple[float, float]:
    """Where the lines through two segments cross"""
    (x1, y1), (x2, y2) = s1
    (x3, y3), (x4, y4) = s2
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-12:
        return _lerp(s1[0], s1[1], 0.5)
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)


def col_segment(frame, u) -> tuple:
    tl, tr, br, bl = frame
    return _lerp(tl, tr, u[0]), _lerp(bl, br, u[1])


def row_segment(frame, v) -> tuple:
    tl, tr, br, bl = frame
    return _lerp(tl, bl, v[0]), _lerp(tr, br, v[1])


def grid_points(grid: dict) -> list[list[tuple[float, float]]]:
    """Corner points indexed [row edge][column edge], outer edges included"""
    frame = grid["frame"]
    cols = [col_segment(frame, c["u"]) for c in grid["cols"]] + [col_segment(frame, (1, 1))]
    rows = [row_segment(frame, r["v"]) for r in grid["rows"]] + [row_segment(frame, (1, 1))]
    return [[_meet(c, r) for c in cols] for r in rows]


# ---- storage

def get_table(conn: sqlite3.Connection, doc_id: int, page: int) -> dict | None:
    row = conn.execute(
        "SELECT grid, rev, updated_at FROM doc_tables WHERE paperless_id=? AND page=?",
        (doc_id, page)).fetchone()
    if row is None:
        return None
    return {"grid": json.loads(row["grid"]), "rev": row["rev"], "updated_at": row["updated_at"]}


def save_table(conn: sqlite3.Connection, doc_id: int, page: int, grid: dict,
               base_rev: int, title: str | None = None) -> dict:
    """Store a normalized grid if the table is still at base_rev (0: no table yet)"""
    text = json.dumps(grid, ensure_ascii=False, separators=(",", ":"))
    now = _now()
    with conn:
        row = conn.execute(
            "SELECT rev FROM doc_tables WHERE paperless_id=? AND page=?", (doc_id, page)).fetchone()
        current = row["rev"] if row else 0
        if current != base_rev:
            raise Conflict(current)
        if row:
            conn.execute(
                "UPDATE doc_tables SET grid=?, rev=?, updated_at=?, title=COALESCE(?, title)"
                " WHERE paperless_id=? AND page=?",
                (text, current + 1, now, title, doc_id, page))
        else:
            conn.execute(
                "INSERT INTO doc_tables (paperless_id, page, title, grid, rev, updated_at)"
                " VALUES (?, ?, ?, ?, 1, ?)",
                (doc_id, page, title, text, now))
    return {"grid": grid, "rev": current + 1, "updated_at": now}


def delete_table(conn: sqlite3.Connection, doc_id: int, page: int, base_rev: int) -> bool:
    """Remove the page's table if it is still at base_rev; its notes stay"""
    with conn:
        row = conn.execute(
            "SELECT rev FROM doc_tables WHERE paperless_id=? AND page=?", (doc_id, page)).fetchone()
        current = row["rev"] if row else 0
        if current != base_rev:
            raise Conflict(current)
        return conn.execute("DELETE FROM doc_tables WHERE paperless_id=? AND page=?",
                            (doc_id, page)).rowcount > 0


def delete_page(conn: sqlite3.Connection, doc_id: int, page: int) -> bool:
    """Remove the page's table and notes"""
    with conn:
        n = conn.execute("DELETE FROM doc_tables WHERE paperless_id=? AND page=?", (doc_id, page)).rowcount
        n += conn.execute("DELETE FROM page_notes WHERE paperless_id=? AND page=?", (doc_id, page)).rowcount
    return n > 0


def doc_options(conn: sqlite3.Connection, doc_id: int) -> dict:
    """The document's viewer options; translations default to on when any page has some"""
    row = conn.execute("SELECT options FROM doc_options WHERE paperless_id=?", (doc_id,)).fetchone()
    stored = json.loads(row["options"]) if row else {}
    if "translations" not in stored:
        stored["translations"] = any(
            grid.get("trans") or any(c.get("trans") for c in grid["cols"])
            for grid in (json.loads(r["grid"]) for r in conn.execute(
                "SELECT grid FROM doc_tables WHERE paperless_id=?", (doc_id,))))
    return {"translations": bool(stored["translations"])}


def set_doc_options(conn: sqlite3.Connection, doc_id: int, translations: bool) -> dict:
    with conn:
        conn.execute(
            "INSERT INTO doc_options (paperless_id, options) VALUES (?, ?)"
            " ON CONFLICT(paperless_id) DO UPDATE SET options=excluded.options",
            (doc_id, json.dumps({"translations": bool(translations)})))
    return doc_options(conn, doc_id)


def table_pages(conn: sqlite3.Connection, doc_id: int) -> list[int]:
    return [r["page"] for r in conn.execute(
        "SELECT page FROM doc_tables WHERE paperless_id=? ORDER BY page", (doc_id,))]


def set_title(conn: sqlite3.Connection, doc_id: int, title: str) -> None:
    with conn:
        for table in ("doc_tables", "page_notes"):
            conn.execute(f"UPDATE {table} SET title=? WHERE paperless_id=? AND title IS NOT ?",
                         (title, doc_id, title))


def list_tables(conn: sqlite3.Connection) -> list[dict]:
    """Every page with a table or notes, most recently changed first"""
    notes = {(r["paperless_id"], r["page"]): r for r in conn.execute(
        "SELECT paperless_id, page, MAX(title) AS title, COUNT(*) AS n, MAX(updated_at) AS latest"
        " FROM page_notes GROUP BY paperless_id, page")}
    out = []
    for row in conn.execute("SELECT paperless_id, page, title, grid, updated_at FROM doc_tables"):
        grid = json.loads(row["grid"])
        note = notes.pop((row["paperless_id"], row["page"]), None)
        out.append({
            "doc_id": row["paperless_id"], "page": row["page"], "title": row["title"] or "",
            "table": True, "lines": len(grid["rows"]), "columns": len(grid["cols"]),
            "filled": sum(len(v) for v in grid["cells"].values()),
            "notes": note["n"] if note else 0,
            "updated_at": max(row["updated_at"], note["latest"]) if note else row["updated_at"],
        })
    for (doc_id, page), note in notes.items():
        out.append({
            "doc_id": doc_id, "page": page, "title": note["title"] or "",
            "table": False, "lines": 0, "columns": 0, "filled": 0,
            "notes": note["n"], "updated_at": note["latest"],
        })
    out.sort(key=lambda t: (t["updated_at"], -t["doc_id"], -t["page"]), reverse=True)
    return out


# ---- notes pinned to page points

def _note(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in ("id", "x", "y", "text", "created_at", "updated_at")}


def _note_text(text) -> str:
    out = str(text or "").strip()
    if not out:
        raise ValueError("a note needs text")
    if len(out) > NOTE_MAX:
        raise ValueError(f"a note is longer than {NOTE_MAX} characters")
    return out


def list_notes(conn: sqlite3.Connection, doc_id: int, page: int) -> list[dict]:
    return [_note(r) for r in conn.execute(
        "SELECT * FROM page_notes WHERE paperless_id=? AND page=? ORDER BY id", (doc_id, page))]


def get_note(conn: sqlite3.Connection, note_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM page_notes WHERE id=?", (note_id,)).fetchone()
    return _note(row) if row else None


def add_note(conn: sqlite3.Connection, doc_id: int, page: int, x, y, text,
             title: str | None = None) -> dict:
    point = (_unit(x, "x"), _unit(y, "y"))
    body = _note_text(text)
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO page_notes (paperless_id, page, title, x, y, text, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (doc_id, page, title, *point, body, now, now))
    return get_note(conn, cur.lastrowid)


def update_note(conn: sqlite3.Connection, note_id: int, text=None, x=None, y=None) -> dict | None:
    """New text and/or position; only a text change counts as an update"""
    if get_note(conn, note_id) is None:
        return None
    with conn:
        if text is not None:
            conn.execute("UPDATE page_notes SET text=?, updated_at=? WHERE id=?",
                         (_note_text(text), _now(), note_id))
        if x is not None or y is not None:
            note = get_note(conn, note_id)
            conn.execute("UPDATE page_notes SET x=?, y=? WHERE id=?",
                         (_unit(note["x"] if x is None else x, "x"),
                          _unit(note["y"] if y is None else y, "y"), note_id))
    return get_note(conn, note_id)


def delete_note(conn: sqlite3.Connection, note_id: int) -> bool:
    with conn:
        return conn.execute("DELETE FROM page_notes WHERE id=?", (note_id,)).rowcount > 0


# ---- page images

_PDFIUM = threading.Lock()


class _Lru:
    def __init__(self, size: int) -> None:
        self.size = size
        self._items: OrderedDict = OrderedDict()

    def get(self, key):
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key, value) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.size:
            self._items.popitem(last=False)


SOURCES = _Lru(3)
IMAGES = _Lru(16)
COUNTS = _Lru(512)


def source_kind(doc: dict) -> str | None:
    """'original', 'archive', or None when there is nothing Bifrost can draw"""
    mime = doc.get("mime_type") or ""
    if mime == "application/pdf" or mime in RASTER_MIMES:
        return "original"
    if doc.get("archived_file_name"):
        return "archive"
    return None


def version_key(doc: dict) -> str:
    """Changes whenever the document's file may have"""
    sums = sorted(str(v.get("checksum", "")) for v in doc.get("versions") or [] if isinstance(v, dict))
    return hashlib.sha1(f"{doc.get('modified', '')}|{'|'.join(sums)}".encode()).hexdigest()[:12]


def _pdf_scale(page) -> float:
    """Pixels per point that keep the page's largest image at its own resolution"""
    import pypdfium2.raw as pdfium_c
    best_area, scale = 0.0, DEFAULT_DPI / 72
    for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,), max_depth=2):
        try:
            w_px, h_px = obj.get_px_size()
            left, bottom, right, top = obj.get_bounds()
        except Exception:  # noqa: BLE001
            continue
        w_pt, h_pt = right - left, top - bottom
        if w_pt <= 0 or h_pt <= 0 or w_pt * h_pt <= best_area:
            continue
        best_area, scale = w_pt * h_pt, max(w_px, h_px) / max(w_pt, h_pt)
    return min(MAX_DPI / 72, max(MIN_DPI / 72, scale))


def page_count(data: bytes, mime: str) -> int:
    if mime == "application/pdf":
        import pypdfium2 as pdfium
        with _PDFIUM:
            pdf = pdfium.PdfDocument(data)
            try:
                return len(pdf)
            finally:
                pdf.close()
    from PIL import Image
    with Image.open(io.BytesIO(data)) as img:
        return getattr(img, "n_frames", 1)


def page_image(data: bytes, mime: str, page: int):
    """The page as a PIL image, turned the way a browser shows it"""
    if mime == "application/pdf":
        import pypdfium2 as pdfium
        with _PDFIUM:
            try:
                pdf = pdfium.PdfDocument(data)
            except pdfium.PdfiumError as exc:
                raise PageError(f"not a readable PDF: {exc}") from exc
            try:
                if not 1 <= page <= len(pdf):
                    raise PageError(f"no page {page}")
                pg = pdf[page - 1]
                w, h = pg.get_size()
                img = pg.render(scale=min(_pdf_scale(pg), MAX_SIDE / max(w, h, 1))).to_pil()
                pg.close()
                return img
            finally:
                pdf.close()
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as exc:
        raise PageError("not a readable image") from exc
    try:
        img.seek(page - 1)
    except (EOFError, ValueError):
        raise PageError(f"no page {page}") from None
    img = ImageOps.exif_transpose(img)
    return img if img.mode in ("RGB", "L") else img.convert("RGB")


def _jpeg(img, quality: int = 90) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def page_bytes(data: bytes, mime: str, page: int) -> tuple[bytes, str]:
    """What the browser draws for a page: the file itself when it can"""
    if mime in BROWSER_MIMES and page == 1:
        return data, mime
    return _jpeg(page_image(data, mime, page)), "image/jpeg"


async def source(paperless: PaperlessClient, doc: dict) -> tuple[bytes, str]:
    kind = source_kind(doc)
    if kind is None:
        raise PageError(f"Bifrost can't draw a {doc.get('mime_type') or 'file of unknown type'}")
    key = (doc["id"], version_key(doc))
    hit = SOURCES.get(key)
    if hit:
        return hit
    if kind == "original":
        data, mime = await paperless.download_original(doc["id"])
        if mime not in RASTER_MIMES and mime != "application/pdf":
            mime = doc.get("mime_type") or mime
    else:
        data, mime = await paperless.download_archive(doc["id"])
    SOURCES.put(key, (data, mime))
    return data, mime


async def pages(paperless: PaperlessClient, doc: dict) -> int:
    """Pages in the file Bifrost draws"""
    mime = doc.get("mime_type")
    if source_kind(doc) == "original" and len(doc.get("versions") or []) < 2:
        if mime == "application/pdf" and doc.get("page_count"):
            return int(doc["page_count"])
        if mime in BROWSER_MIMES:
            return 1
    key = (doc["id"], version_key(doc))
    hit = COUNTS.get(key)
    if hit is not None:
        return hit
    data, mime = await source(paperless, doc)
    try:
        n = await asyncio.to_thread(page_count, data, mime)
    except Exception as exc:  # noqa: BLE001
        raise PageError(f"unreadable file: {exc}") from exc
    COUNTS.put(key, n)
    return n


async def page_file(paperless: PaperlessClient, doc: dict, page: int) -> tuple[bytes, str]:
    key = (doc["id"], version_key(doc), page)
    hit = IMAGES.get(key)
    if hit:
        return hit
    data, mime = await source(paperless, doc)
    out = await asyncio.to_thread(page_bytes, data, mime, page)
    IMAGES.put(key, out)
    return out


async def page_pil(paperless: PaperlessClient, doc: dict, page: int):
    data, mime = await source(paperless, doc)
    return await asyncio.to_thread(page_image, data, mime, page)


# ---- transcription

def bands(grid: dict, row_ids: list[str] | None) -> list[tuple[int, int]]:
    """Runs of at most BAND_ROWS wanted rows that still have an empty cell, as [lo, hi)"""
    wanted = None if row_ids is None else set(row_ids)
    n = len(grid["cols"])
    out: list[tuple[int, int]] = []
    for j, r in enumerate(grid["rows"]):
        if wanted is not None and r["id"] not in wanted:
            continue
        if len(grid["cells"].get(r["id"], {})) >= n:
            continue
        if out and out[-1][1] == j and j - out[-1][0] < BAND_ROWS:
            out[-1] = (out[-1][0], j + 1)
        else:
            out.append((j, j + 1))
    return out


def band_image(img, grid: dict, lo: int, hi: int) -> bytes:
    """Rows lo..hi-1 cut from the page, cells outlined, lines numbered and columns keyed"""
    from PIL import Image, ImageDraw, ImageFont
    w, h = img.size
    pts = [[(x * w, y * h) for x, y in edge] for edge in grid_points(grid)[lo:hi + 1]]
    xs = [p[0] for edge in pts for p in edge]
    ys = [p[1] for edge in pts for p in edge]
    row_h = (max(ys) - min(ys)) / (hi - lo)
    pad = max(6.0, row_h * 0.2)
    x0, y0 = max(0, int(min(xs) - pad)), max(0, int(min(ys) - pad))
    x1, y1 = min(w, math.ceil(max(xs) + pad)), min(h, math.ceil(max(ys) + pad))
    size = int(min(40, max(14, row_h * 0.45)))
    font = ImageFont.load_default(size=size)
    side, top = int(size * 3.4), int(size * 2.8)
    out = Image.new("RGB", (x1 - x0 + 2 * side, y1 - y0 + top), "white")
    out.paste(img.crop((x0, y0, x1, y1)).convert("RGB"), (side, top))
    draw = ImageDraw.Draw(out)
    red, width = (220, 0, 0), max(2, size // 8)

    def at(p):
        return (p[0] - x0 + side, p[1] - y0 + top)

    for edge in pts:
        draw.line([at(edge[0]), at(edge[-1])], fill=red, width=width)
    for k in range(len(pts[0])):
        draw.line([at(pts[0][k]), at(pts[-1][k])], fill=red, width=width)
    for j in range(hi - lo):
        label = str(grid["first_line"] + lo + j)
        left = (at(pts[j][0])[1] + at(pts[j + 1][0])[1]) / 2
        right = (at(pts[j][-1])[1] + at(pts[j + 1][-1])[1]) / 2
        draw.text((side / 2, left), label, fill=red, font=font, anchor="mm")
        draw.text((out.width - side / 2, right), label, fill=red, font=font, anchor="mm")
    for k in range(len(pts[0]) - 1):
        cx = (at(pts[0][k])[0] + at(pts[0][k + 1])[0]) / 2
        draw.text((cx, top * (0.3 if k % 2 == 0 else 0.7)), f"c{k + 1}",
                  fill=red, font=font, anchor="mm")
    return _jpeg(out)


def _prompt(grid: dict, lo: int, hi: int) -> str:
    columns = "\n".join(f"c{k + 1}: {c['name'] or '(no name)'}" for k, c in enumerate(grid["cols"]))
    first = grid["first_line"]
    lines = f"line {first + lo}" if hi - lo == 1 else f"lines {first + lo} to {first + hi - 1}"
    return TRANSCRIBE_PROMPT.format(columns=columns, lines=lines)


def _schema(ncols: int) -> dict:
    keys = [f"c{k + 1}" for k in range(ncols)]
    return {
        "type": "OBJECT",
        "properties": {"lines": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"line": {"type": "STRING"}, **{k: {"type": "STRING"} for k in keys}},
            "required": ["line", *keys],
            "propertyOrdering": ["line", *keys],
        }}},
        "required": ["lines"],
    }


def parse_band(answer, grid: dict, lo: int, hi: int) -> dict[str, dict[str, str]]:
    """Gemini's lines as {row id: {column id: value}}, keeping only rows lo..hi-1"""
    rows = {grid["first_line"] + j: grid["rows"][j]["id"] for j in range(lo, hi)}
    out: dict[str, dict[str, str]] = {}
    items = answer.get("lines") if isinstance(answer, dict) else None
    for item in items or []:
        if not isinstance(item, dict):
            continue
        m = re.search(r"-?\d+", str(item.get("line", "")))
        rid = rows.get(int(m.group())) if m else None
        if rid is None:
            continue
        vals = {}
        for k, col in enumerate(grid["cols"]):
            text = item.get(f"c{k + 1}")
            if isinstance(text, str) and text.strip():
                vals[col["id"]] = text.strip()[:VALUE_MAX]
        if vals:
            out.setdefault(rid, {}).update(vals)
    return out


async def transcribe(
    gemini: GeminiClient, img, grid: dict, row_ids: list[str] | None,
    thinking_budget: int | None = None,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Gemini's reading of the wanted rows, band by band, plus one error per failed band"""
    work = bands(grid, row_ids)
    images = await asyncio.to_thread(lambda: [band_image(img, grid, lo, hi) for lo, hi in work])
    schema = _schema(len(grid["cols"]))
    gate = asyncio.Semaphore(CONCURRENCY)
    readings: dict[str, dict[str, str]] = {}
    failed: list[tuple[int, int, str]] = []

    async def one(lo: int, hi: int, data: bytes) -> None:
        async with gate:
            try:
                answer = await gemini.generate_json(
                    [(data, "image/jpeg")], _prompt(grid, lo, hi), schema, thinking_budget)
            except GeminiError as exc:
                failed.append((lo, hi, str(exc)))
                return
        for rid, vals in parse_band(answer, grid, lo, hi).items():
            readings.setdefault(rid, {}).update(vals)

    await asyncio.gather(*(one(lo, hi, data) for (lo, hi), data in zip(work, images)))
    if len(failed) == len(work) and len({msg for *_, msg in failed}) == 1:
        return readings, [failed[0][2]]
    first = grid["first_line"]
    return readings, [f"lines {first + lo}–{first + hi - 1}: {msg}" for lo, hi, msg in sorted(failed)]


def merge_readings(grid: dict, readings: dict[str, dict[str, str]]) -> tuple[dict, int]:
    """Fill only cells that are still empty, in rows and columns that still exist"""
    col_ids = {c["id"] for c in grid["cols"]}
    row_ids = {r["id"] for r in grid["rows"]}
    cells = {rid: dict(vals) for rid, vals in grid["cells"].items()}
    filled = 0
    for rid, vals in readings.items():
        if rid not in row_ids:
            continue
        row = cells.setdefault(rid, {})
        for cid, text in vals.items():
            if cid in col_ids and not row.get(cid):
                row[cid] = text
                filled += 1
        if not row:
            cells.pop(rid)
    return {**grid, "cells": cells}, filled
