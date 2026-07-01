"""The a-series scan register — an append-only log of digitization events.

One row per capture FILE (recto scan, verso scan, re-scan: each its own
number), numbered a000101 upward in scanning order. Numbers are never reused;
deleting a bad scan leaves a permanent gap — the gap itself is information.
This register is a log, not a catalog: object identity lives in the random-6
media id (reserved_ids / Gramps / ArchivesSpace item), physical location in
the call number. See archive-scheme/SCHEME.md §2. The b-series belongs to a
different family tree and is not tracked here.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime

A_SERIES_START = 101
_SCAN_RE = re.compile(r"^a(\d{6})$")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fmt(n: int) -> str:
    return f"a{n:06d}"


def next_scan_no(conn: sqlite3.Connection) -> str:
    """The next free a-number: max + 1 (lexicographic max = numeric max, fixed
    width). An empty register starts the series at a000101."""
    row = conn.execute(
        "SELECT scan_no FROM scan_register ORDER BY scan_no DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return fmt(A_SERIES_START)
    return fmt(int(_SCAN_RE.match(row["scan_no"]).group(1)) + 1)


def register_batch(
    conn: sqlite3.Connection,
    count: int,
    container: str | None = None,
    note: str | None = None,
    captured: str | None = None,
) -> list[str]:
    """Allocate the next `count` a-numbers (a scanning batch shares container /
    note / capture date) and return them in order."""
    count = max(1, min(int(count), 500))
    start = int(_SCAN_RE.match(next_scan_no(conn)).group(1))
    nos = [fmt(n) for n in range(start, start + count)]
    with conn:
        conn.executemany(
            "INSERT INTO scan_register (scan_no, container, role, object_id, captured, note)"
            " VALUES (?, ?, NULL, NULL, ?, ?)",
            [(s, container, captured, note) for s in nos])
    return nos


def set_object_id(conn: sqlite3.Connection, scan_no: str, object_id: str | None) -> bool:
    """Link a scan to the object it captures (promotion), or clear the link.
    Returns False for an unregistered scan number."""
    with conn:
        cur = conn.execute(
            "UPDATE scan_register SET object_id = ? WHERE scan_no = ?",
            (object_id or None, scan_no))
    return cur.rowcount > 0


def overview(conn: sqlite3.Connection, recent: int = 12) -> dict:
    """Register status for the IDs page: next free number, counts, latest rows."""
    total = conn.execute("SELECT COUNT(*) AS n FROM scan_register").fetchone()["n"]
    linked = conn.execute(
        "SELECT COUNT(*) AS n FROM scan_register WHERE object_id IS NOT NULL"
    ).fetchone()["n"]
    rows = [dict(r) for r in conn.execute(
        "SELECT scan_no, container, role, object_id, captured, note"
        " FROM scan_register ORDER BY scan_no DESC LIMIT ?", (recent,))]
    return {"next": next_scan_no(conn), "total": total, "linked": linked, "recent": rows}
