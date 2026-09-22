"""Bifrost-only photo collections whose photos sit in numbered slots"""

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


def slots(conn: sqlite3.Connection, cid: int) -> dict[str, int]:
    """asset id -> slot, in slot order"""
    return {r["asset_id"]: r["seq"] for r in conn.execute(
        "SELECT asset_id, seq FROM collection_items WHERE collection_id=? ORDER BY seq, added_at", (cid,))}


def item_ids(conn: sqlite3.Connection, cid: int) -> list[str]:
    return [r["asset_id"] for r in conn.execute(
        "SELECT asset_id FROM collection_items WHERE collection_id=? ORDER BY seq, added_at", (cid,))]


def _touch(conn: sqlite3.Connection, cid: int) -> None:
    conn.execute("UPDATE collections SET updated_at=? WHERE id=?", (_now(), cid))


def add_items(conn: sqlite3.Connection, cid: int, asset_ids: list[str]) -> int:
    """New ids take the free slots after the last one, then any gaps; ids already present keep theirs"""
    taken = slots(conn, cid)
    new = [a for a in dict.fromkeys(asset_ids) if a and a not in taken]
    if len(taken) + len(new) > MAX_ITEMS:
        raise ValueError(f"a collection holds at most {MAX_ITEMS} photos")
    if not new:
        return 0
    used = set(taken.values())
    last = max(used, default=0)
    free = [*range(last + 1, MAX_ITEMS + 1), *(s for s in range(1, last) if s not in used)]
    with conn:
        for asset_id, slot in zip(new, free):
            conn.execute(
                "INSERT INTO collection_items (collection_id, asset_id, seq, added_at) VALUES (?, ?, ?, ?)",
                (cid, asset_id, slot, _now()))
        _touch(conn, cid)
    return len(new)


def remove_item(conn: sqlite3.Connection, cid: int, asset_id: str) -> bool:
    with conn:
        cur = conn.execute("DELETE FROM collection_items WHERE collection_id=? AND asset_id=?",
                           (cid, asset_id))
        if cur.rowcount:
            _touch(conn, cid)
    return cur.rowcount > 0


def move_item(conn: sqlite3.Connection, cid: int, asset_id: str, slot: int) -> dict[str, int] | None:
    """Put one item in a slot from 1 to MAX_ITEMS, swapping with a photo already there; None if it is not in the collection"""
    current = slots(conn, cid)
    if asset_id not in current:
        return None
    slot = min(max(slot, 1), MAX_ITEMS)
    other = next((a for a, s in current.items() if s == slot and a != asset_id), None)
    with conn:
        if other:
            conn.execute("UPDATE collection_items SET seq=? WHERE collection_id=? AND asset_id=?",
                         (current[asset_id], cid, other))
        conn.execute("UPDATE collection_items SET seq=? WHERE collection_id=? AND asset_id=?",
                     (slot, cid, asset_id))
        _touch(conn, cid)
    return slots(conn, cid)


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
