"""Scan-role metadata stored in Immich per-asset metadata (gda.scan).

Mirrors the media ID scheme (SCHEME.md v2): a 6-char safe-alphabet base
object id plus a role suffix — bare (Gramps copy), _o (original),
_c## (crop/derived), _d## (duplicate), _v## (verso), _a## (AI-edited) — with
plain-decimal ordinals, and optionally the a-series scan number of the capture.

Stored shape (schema 1):
    {"schema": 1, "base": "VGRN54", "role": "v", "ordinal": 1,
     "scan_no": "a000277", "label": "VGRN54_v01"}
"""

from __future__ import annotations

import re

from .. import ids

ROLES = {
    "bare": "Canonical copy (base id, no suffix)",
    "o": "Original (unedited master)",
    "c": "Crop / detail",
    "d": "Duplicate (extra print / full copy)",
    "v": "Verso (back of print)",
    "a": "AI-edited",
}

_ORDINAL_ROLES = frozenset({"c", "d", "v", "a"})
_BASE_RE = re.compile(rf"^[{ids.CHARSET}]{{6}}$")
_SCAN_NO_RE = re.compile(r"^a\d{6}$")


class ScanError(ValueError):
    pass


def _label(base: str, role: str, ordinal: int | None) -> str:
    if role == "bare":
        return base
    if role == "o":
        return f"{base}_o"
    return f"{base}_{role}{ordinal:02d}"


def validate(payload: object) -> dict:
    """Normalize a scan-role payload from the editor; raise ScanError when invalid."""
    if not isinstance(payload, dict):
        raise ScanError("expected a scan object")

    base = str(payload.get("base") or "").strip().upper()
    if not _BASE_RE.match(base):
        raise ScanError("base id must be 6 chars from the safe alphabet (no I/L/O/0/1)")

    role = payload.get("role") or "bare"
    if role not in ROLES:
        raise ScanError(f"unknown role: {role!r}")

    ordinal = payload.get("ordinal")
    if role in _ORDINAL_ROLES:
        try:
            ordinal = int(ordinal)
        except (TypeError, ValueError) as exc:
            raise ScanError("this role needs an ordinal (1-99)") from exc
        if not 1 <= ordinal <= 99:
            raise ScanError("ordinal must be 1-99")
    else:
        ordinal = None

    scan_no = str(payload.get("scan_no") or "").strip().lower()
    if scan_no and not _SCAN_NO_RE.match(scan_no):
        raise ScanError("scan number looks like a000277")

    return {
        "schema": 1,
        "base": base,
        "role": role,
        "ordinal": ordinal,
        "scan_no": scan_no or None,
        "label": _label(base, role, ordinal),
    }
