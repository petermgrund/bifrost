"""The random-6 media-id generator and manual-id validation.

One shared home for the safe alphabet (no I/O/L/0/1 — unambiguous when
hand-written on a photo verso) used by media ids, note ids, and handles.
See docs/MEDIA_ID_SCHEME.md and archive-scheme/SCHEME.md §1.
"""

from __future__ import annotations

import re
import secrets

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


def validate_manual_ids(
    manual_ids: dict | None, taken: set[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Split a {source_id: chosen_id} map into (valid, rejected{source_id: reason}).

    A valid id matches the media-id format (6 chars of the safe alphabet), is not
    already in Gramps, and is unique within the batch. Blank entries are ignored
    (that asset just gets an auto id). Reserved-but-unminted ids are accepted —
    `taken` is the set of ids already realized in Gramps, not the reservation pool.
    """
    valid: dict[str, str] = {}
    rejected: dict[str, str] = {}
    claimed: set[str] = set()
    for sid, raw in (manual_ids or {}).items():
        gid = (raw or "").strip()
        if not gid:
            continue
        if not MANUAL_ID_RE.match(gid):
            rejected[sid] = f"invalid id '{gid}' — need 6 chars from {CHARSET}"
        elif gid in taken:
            rejected[sid] = f"id '{gid}' is already in use"
        elif gid in claimed:
            rejected[sid] = f"id '{gid}' assigned to more than one asset"
        else:
            claimed.add(gid)
            valid[sid] = gid
    return valid, rejected
