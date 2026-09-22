"""Bifrost-only photo collections with a manual order"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

MAX_ITEMS = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "name": r["name"], "description": r["description"] or "",
            "created_at": r["created_at"], "updated_at": r["updated_at"]}


def list_all(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM collection_items i WHERE i.collection_id=c.id) AS count, "
        "(SELECT asset_id FROM collection_items i WHERE i.collection_id=c.id ORDER BY seq LIMIT 1) AS cover "
        "FROM collections c ORDER BY lower(c.name), c.id").fetchall()
    return [{**_row(r), "count": r["count"], "cover": r["cover"]} for r in rows]


def get(conn: sqlite3.Connection, cid: int) -> dict | None:
    r = conn.execute("SELECT * FROM collections WHERE id=?", (cid,)).fetchone()
    return _row(r) if r else None


def create(conn: sqlite3.Connection, name: str, description: str = "") -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("a collection needs a name")
    with conn:
        cur = conn.execute(
            "INSERT INTO collections (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (name, (description or "").strip(), _now(), _now()))
    return get(conn, cur.lastrowid)


def update(conn: sqlite3.Connection, cid: int, name: str, description: str) -> dict | None:
    name = (name or "").strip()
    if not name:
        raise ValueError("a collection needs a name")
    with conn:
        conn.execute("UPDATE collections SET name=?, description=?, updated_at=? WHERE id=?",
                     (name, (description or "").strip(), _now(), cid))
    return get(conn, cid)


def delete(conn: sqlite3.Connection, cid: int) -> bool:
    with conn:
        cur = conn.execute("DELETE FROM collections WHERE id=?", (cid,))
    return cur.rowcount > 0


def item_ids(conn: sqlite3.Connection, cid: int) -> list[str]:
    return [r["asset_id"] for r in conn.execute(
        "SELECT asset_id FROM collection_items WHERE collection_id=? ORDER BY seq, added_at", (cid,))]


def _touch(conn: sqlite3.Connection, cid: int) -> None:
    conn.execute("UPDATE collections SET updated_at=? WHERE id=?", (_now(), cid))


def add_items(conn: sqlite3.Connection, cid: int, asset_ids: list[str]) -> int:
    """Append the new ids in the given order; ids already present keep their place"""
    current = item_ids(conn, cid)
    new = [a for a in dict.fromkeys(asset_ids) if a and a not in set(current)]
    if len(current) + len(new) > MAX_ITEMS:
        raise ValueError(f"a collection holds at most {MAX_ITEMS} photos")
    if not new:
        return 0
    seq = len(current)
    with conn:
        for i, asset_id in enumerate(new):
            conn.execute(
                "INSERT INTO collection_items (collection_id, asset_id, seq, added_at) VALUES (?, ?, ?, ?)",
                (cid, asset_id, seq + i, _now()))
        _touch(conn, cid)
    return len(new)


def remove_item(conn: sqlite3.Connection, cid: int, asset_id: str) -> bool:
    with conn:
        cur = conn.execute("DELETE FROM collection_items WHERE collection_id=? AND asset_id=?",
                           (cid, asset_id))
        if cur.rowcount:
            _touch(conn, cid)
    return cur.rowcount > 0


def reorder(conn: sqlite3.Connection, cid: int, asset_ids: list[str]) -> list[str]:
    """The listed ids first, in that order; anything unlisted keeps its old relative order after them"""
    current = item_ids(conn, cid)
    present = set(current)
    wanted = [a for a in dict.fromkeys(asset_ids) if a in present]
    wanted += [a for a in current if a not in set(wanted)]
    with conn:
        for i, asset_id in enumerate(wanted):
            conn.execute("UPDATE collection_items SET seq=? WHERE collection_id=? AND asset_id=?",
                         (i, cid, asset_id))
        _touch(conn, cid)
    return wanted


def move_item(conn: sqlite3.Connection, cid: int, asset_id: str, position: int) -> list[str] | None:
    """Put one item at a 1-based position, clamped to the collection; None if it is not in it"""
    current = item_ids(conn, cid)
    if asset_id not in current:
        return None
    order = [a for a in current if a != asset_id]
    order.insert(min(max(position, 1), len(current)) - 1, asset_id)
    return reorder(conn, cid, order)


def for_asset(conn: sqlite3.Connection, asset_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT c.id, c.name FROM collection_items i JOIN collections c ON c.id=i.collection_id "
        "WHERE i.asset_id=? ORDER BY lower(c.name), c.id", (asset_id,)).fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def move_items(conn: sqlite3.Connection, old_asset: str, new_asset: str) -> int:
    """Memberships follow a photo's new main image"""
    moved = 0
    with conn:
        for r in conn.execute("SELECT collection_id, seq FROM collection_items WHERE asset_id=?",
                              (old_asset,)).fetchall():
            cid = r["collection_id"]
            if conn.execute("SELECT 1 FROM collection_items WHERE collection_id=? AND asset_id=?",
                            (cid, new_asset)).fetchone():
                conn.execute("DELETE FROM collection_items WHERE collection_id=? AND asset_id=?",
                             (cid, old_asset))
            else:
                conn.execute("UPDATE collection_items SET asset_id=? WHERE collection_id=? AND asset_id=?",
                             (new_asset, cid, old_asset))
            moved += 1
    return moved
