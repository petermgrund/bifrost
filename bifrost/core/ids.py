from __future__ import annotations

import re
import secrets
import sqlite3
from typing import Iterable

CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

MANUAL_ID_RE = re.compile(rf"^[{CHARSET}]{{6}}$")

# pre-scheme 4-char codes (archivesspace/registry/ids.txt), closed list
LEGACY_IDS = frozenset({"C8T5", "J82D", "JYMZ", "6H2P", "G8NQ"})


class IdReused(sqlite3.IntegrityError):
    """A minted id is already in the register"""


def generate_gramps_id(existing: set[str], length: int = 6) -> str:
    for _ in range(1000):
        candidate = "".join(secrets.choice(CHARSET) for _ in range(length))
        if candidate not in existing:
            existing.add(candidate)
            return candidate
    raise RuntimeError("Failed to generate gramps_id")


def generate_handle() -> str:
    return "".join(secrets.choice(CHARSET) for _ in range(16))


def all_ids_ever_seen(
    conn: sqlite3.Connection,
    live: Iterable[str] = (),
    paperless: Iterable[str | None] = (),
    *,
    open_reservations: bool = True,
) -> set[str]:
    """Every id that must never be handed out again

    live Gramps media ids, every reservation in any state, every register row
    (also when its media is gone from Gramps), scan-register object ids,
    Paperless gramps_id field values and the legacy codes.
    open_reservations=False leaves out reservations not minted yet, so a
    manual id can claim its own reservation
    """
    queries = (
        "SELECT gramps_id FROM minted_media",
        "SELECT object_id FROM scan_register WHERE object_id IS NOT NULL",
        "SELECT gramps_id FROM reserved_ids"
        + ("" if open_reservations else " WHERE minted_at IS NOT NULL"),
    )
    stored = (r[0] for q in queries for r in conn.execute(q))
    return {str(v).strip().upper() for v in (*LEGACY_IDS, *stored, *live, *paperless)
            if v and str(v).strip()}


def register_minted(conn: sqlite3.Connection, gramps_id: str, source_system: str,
                    source_id: str, title: str | None, when: str) -> None:
    """Record a minted id, never overwriting an existing row"""
    try:
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (gramps_id, source_system, source_id, title, when),
        )
    except sqlite3.IntegrityError:
        row = conn.execute(
            "SELECT source_system, source_id FROM minted_media WHERE gramps_id=?",
            (gramps_id,),
        ).fetchone()
        if row is None:
            raise
        raise IdReused(
            f"{gramps_id} is already registered to {row[0]} {row[1]}, not overwritten"
        ) from None


def mark_minted(conn: sqlite3.Connection, gramps_id: str, when: str) -> None:
    """Flip a reservation to minted"""
    conn.execute(
        "UPDATE reserved_ids SET minted_at=? WHERE gramps_id=? AND minted_at IS NULL",
        (when, gramps_id),
    )
