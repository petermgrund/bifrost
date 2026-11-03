from __future__ import annotations

import re
import secrets
import sqlite3
from typing import Iterable

CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

MANUAL_ID_RE = re.compile(rf"^[{CHARSET}]{{6}}$")

STOP_WORDS = frozenset({"README", "SCHEME"})


class IdReused(sqlite3.IntegrityError):
    """A minted id is already in the register"""


def guard_reason(code: str) -> str | None:
    if re.fullmatch(r"[0-9]+", code):
        return "is all digits, like a Paperless document number"
    if code in STOP_WORDS:
        return "is a reserved word"
    return None


def generate_gramps_id(existing: set[str], length: int = 6) -> str:
    for _ in range(1000):
        candidate = "".join(secrets.choice(CHARSET) for _ in range(length))
        if candidate not in existing and not guard_reason(candidate):
            existing.add(candidate)
            return candidate
    raise RuntimeError("Failed to generate gramps_id")


def generate_handle() -> str:
    return "".join(secrets.choice(CHARSET) for _ in range(16))


def next_sequential_id(prefix: str, existing: set[str]) -> str:
    pat = re.compile(rf"^{prefix}(\d+)$")
    nums = [int(m.group(1)) for i in existing if (m := pat.match(i))]
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:04d}"


def all_ids_ever_seen(
    conn: sqlite3.Connection,
    live: Iterable[str] = (),
    paperless: Iterable[str | None] = (),
    *,
    open_reservations: bool = True,
) -> set[str]:
    query = "SELECT gramps_id FROM minted_media"
    if not open_reservations:
        query += " WHERE source_system IS NOT NULL OR withdrawn_at IS NOT NULL"
    stored = {r[0] for r in conn.execute(query)}
    return {str(v).strip().upper() for v in (*stored, *live, *paperless)
            if v and str(v).strip()}


def register_minted(conn: sqlite3.Connection, gramps_id: str, source_system: str,
                    source_id: str, when: str) -> None:
    row = conn.execute(
        "SELECT source_system, source_id, withdrawn_at FROM minted_media WHERE gramps_id=?",
        (gramps_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, created_at, minted_at) "
            "VALUES (?, ?, ?, ?, ?)", (gramps_id, source_system, source_id, when, when))
        return
    if row[0] is not None:
        raise IdReused(f"{gramps_id} is already registered to {row[0]} {row[1]}, not overwritten")
    if row[2]:
        raise IdReused(f"{gramps_id} was withdrawn on {row[2][:10]} and is never used again")
    conn.execute(
        "UPDATE minted_media SET source_system=?, source_id=?, minted_at=? WHERE gramps_id=?",
        (source_system, source_id, when, gramps_id))
