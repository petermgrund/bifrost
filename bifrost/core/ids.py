from __future__ import annotations

import re
import secrets
import sqlite3

CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

MANUAL_ID_RE = re.compile(rf"^[{CHARSET}]{{6}}$")


def generate_gramps_id(existing: set[str], length: int = 6) -> str:
    for _ in range(1000):
        candidate = "".join(secrets.choice(CHARSET) for _ in range(length))
        if candidate not in existing:
            existing.add(candidate)
            return candidate
    raise RuntimeError("Failed to generate gramps_id")


def generate_handle() -> str:
    return "".join(secrets.choice(CHARSET) for _ in range(16))


def unminted_reserved(conn: sqlite3.Connection) -> set[str]:
    """Reserved-but-unminted ids — excluded from auto-generation, valid as
    manual picks (that's what a reservation is for)."""
    rows = conn.execute(
        "SELECT gramps_id FROM reserved_ids WHERE minted_at IS NULL"
    ).fetchall()
    return {r[0] for r in rows}


def mark_minted(conn: sqlite3.Connection, gramps_id: str, when: str) -> None:
    """Flip a reservation to minted; no-op for ids that were never reserved.
    Caller owns the transaction."""
    conn.execute(
        "UPDATE reserved_ids SET minted_at=? WHERE gramps_id=? AND minted_at IS NULL",
        (when, gramps_id),
    )
