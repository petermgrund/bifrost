"""The random-6 media-id and handle generators.

One shared home for the safe alphabet (no I/O/L/0/1 — unambiguous when
hand-written on a photo verso) used by media ids, note ids, and handles.
See docs/MEDIA_ID_SCHEME.md.
"""

from __future__ import annotations

import secrets

CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_gramps_id(existing: set[str], length: int = 6) -> str:
    for _ in range(1000):
        candidate = "".join(secrets.choice(CHARSET) for _ in range(length))
        if candidate not in existing:
            existing.add(candidate)
            return candidate
    raise RuntimeError("Failed to generate gramps_id")


def generate_handle() -> str:
    return "".join(secrets.choice(CHARSET) for _ in range(16))
