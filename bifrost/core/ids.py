from __future__ import annotations

import re
import secrets
import sqlite3
from typing import Iterable

CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

MANUAL_ID_RE = re.compile(rf"^[{CHARSET}]{{6}}$")

# pre-scheme 4-char codes (archivesspace/registry/ids.txt), closed list. Migration 15
# seeds withdrawn_codes with them; from then on that table is the authority
LEGACY_IDS = frozenset({"C8T5", "J82D", "JYMZ", "6H2P", "G8NQ"})

# an undotted location mark (B2C3F4 = box 2, compartment 3, folder 1; S1 = shelf 1).
# Anchored: real ids that merely start with B or S and a digit, like B36Z55, pass
LOCATION_SHAPE_RE = re.compile(r"^[BS][1-9][0-9]*(C[1-9][0-9]*)?(F[1-9][0-9]*)?$")
STOP_WORDS = frozenset({"README", "SCHEME"})


class IdReused(sqlite3.IntegrityError):
    """A minted id is already in the register"""


def guard_reason(code: str) -> str | None:
    """Why an otherwise well-formed id must never be issued, or None"""
    if re.fullmatch(r"[0-9]+", code):
        return "is all digits, like a Paperless document number"
    if LOCATION_SHAPE_RE.match(code):
        dotted = re.sub(r"(?<=[0-9])(?=[CF])", ".", code)
        return f"looks like the location mark {dotted}"
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
    """Every id that must never be handed out again

    live Gramps media ids, every reservation in any state, every register row
    (also when its media is gone from Gramps), scan-register object ids,
    described objects, Paperless gramps_id field values and withdrawn codes.
    open_reservations=False leaves out reservations not minted (or withdrawn)
    yet, even when a scan or a description already points at them, so a
    manual id can claim its own reservation
    """
    queries = (
        "SELECT gramps_id FROM minted_media",
        "SELECT object_id FROM scan_register WHERE object_id IS NOT NULL",
        "SELECT gramps_id FROM reserved_ids",
        "SELECT object_id FROM objects",
        "SELECT code FROM withdrawn_codes",
    )
    stored = {r[0] for q in queries for r in conn.execute(q)}
    if not open_reservations:
        stored -= {r[0] for r in conn.execute(
            "SELECT gramps_id FROM reserved_ids WHERE minted_at IS NULL "
            "AND gramps_id NOT IN (SELECT gramps_id FROM minted_media) "
            "AND gramps_id NOT IN (SELECT code FROM withdrawn_codes)")}
    return {str(v).strip().upper() for v in (*stored, *live, *paperless)
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
