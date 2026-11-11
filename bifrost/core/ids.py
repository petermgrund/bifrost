from __future__ import annotations

import re
import secrets
from typing import Iterable

CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

MANUAL_ID_RE = re.compile(rf"^[{CHARSET}]{{6}}$")

STOP_WORDS = frozenset({"README", "SCHEME"})


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


def taken_ids(*sources: Iterable[str | None]) -> set[str]:
    """Every id a new code must avoid, normalized"""
    return {str(v).strip().upper() for source in sources for v in source if v and str(v).strip()}
