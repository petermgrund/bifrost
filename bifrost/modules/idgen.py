"""Media-ID generator + reservation ledger.

The ID-generator tab mints random-6 media ids ahead of time so Peter can write
them on photo versos / name files (see docs/MEDIA_ID_SCHEME.md) and later assign
them by hand during a sync. Every id the UI produces is RESERVED: the sync
auto-generator unions the unminted reservations into its "taken" set so it never
picks one, but manual id entry at sync time deliberately accepts reserved ids.
minted_at flips when the id is really created in Gramps.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from ..core.clients import GrampsClient
from .sync_immich import generate_gramps_id


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def reserved_ids(conn: sqlite3.Connection) -> set[str]:
    """Every id the UI has ever generated (minted or not)."""
    return {r["gramps_id"] for r in conn.execute("SELECT gramps_id FROM reserved_ids")}


def unminted_reserved(conn: sqlite3.Connection) -> set[str]:
    """Reserved ids not yet created in Gramps — excluded from the auto-generator."""
    return {r["gramps_id"] for r in conn.execute(
        "SELECT gramps_id FROM reserved_ids WHERE minted_at IS NULL")}


def mark_minted(conn: sqlite3.Connection, gramps_id: str) -> None:
    """Stamp a reserved id as minted (no-op if it isn't a reservation)."""
    with conn:
        conn.execute(
            "UPDATE reserved_ids SET minted_at = ? WHERE gramps_id = ? AND minted_at IS NULL",
            (_now(), gramps_id))


async def generate(conn: sqlite3.Connection, gramps: GrampsClient, count: int) -> list[str]:
    """Mint `count` fresh random-6 ids that collide with neither existing Gramps
    media nor any prior reservation, and record them as reserved."""
    count = max(1, min(int(count), 50))
    pool = await gramps.list_media_gramps_ids() | reserved_ids(conn)
    now = _now()
    new_ids = []
    for _ in range(count):
        gid = generate_gramps_id(pool)  # mutates pool, so the next pick differs
        new_ids.append(gid)
    with conn:
        conn.executemany(
            "INSERT INTO reserved_ids (gramps_id, created_at, minted_at, note)"
            " VALUES (?, ?, NULL, NULL)",
            [(g, now) for g in new_ids])
    return new_ids


def release(conn: sqlite3.Connection, gramps_id: str) -> bool:
    """Delete an unminted reservation. Returns False if it was already minted."""
    with conn:
        cur = conn.execute(
            "DELETE FROM reserved_ids WHERE gramps_id = ? AND minted_at IS NULL",
            (gramps_id,))
    return cur.rowcount > 0


def assign(conn: sqlite3.Connection, gramps_id: str) -> bool:
    """Mark a reserved id as physically assigned (e.g. written on a photo verso)
    but not yet minted. No-op once minted; returns False if the id isn't an
    un-minted reservation."""
    with conn:
        cur = conn.execute(
            "UPDATE reserved_ids SET assigned_at = ? "
            "WHERE gramps_id = ? AND minted_at IS NULL",
            (_now(), gramps_id))
    return cur.rowcount > 0


def unassign(conn: sqlite3.Connection, gramps_id: str) -> bool:
    """Clear the assigned flag, returning an id to plain reserved. No-op once
    minted; returns False if the id isn't an un-minted reservation."""
    with conn:
        cur = conn.execute(
            "UPDATE reserved_ids SET assigned_at = NULL "
            "WHERE gramps_id = ? AND minted_at IS NULL",
            (gramps_id,))
    return cur.rowcount > 0


async def listing(conn: sqlite3.Connection, gramps: GrampsClient) -> list[dict]:
    """All reservations with live minted-status reconciliation and, for minted
    ones, what they became (from minted_media)."""
    live = await gramps.list_media_gramps_ids()
    minted_src = {
        r["gramps_id"]: (r["source_system"], r["title"])
        for r in conn.execute("SELECT gramps_id, source_system, title FROM minted_media")
    }
    rows = []
    for r in conn.execute(
            "SELECT gramps_id, created_at, minted_at, assigned_at FROM reserved_ids "
            "ORDER BY created_at DESC, gramps_id"):
        gid = r["gramps_id"]
        is_minted = bool(r["minted_at"]) or gid in live
        src = minted_src.get(gid)
        rows.append({
            "gramps_id": gid,
            "created_at": r["created_at"],
            "minted": is_minted,
            "minted_at": r["minted_at"],
            # "assigned" only matters while still un-minted; minting supersedes it.
            "assigned": bool(r["assigned_at"]) and not is_minted,
            "assigned_at": r["assigned_at"],
            "source_system": src[0] if src else None,
            "source_title": src[1] if src else None,
        })
    return rows
