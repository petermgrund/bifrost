"""Gramps-model fuzzy dates stored in Immich per-asset metadata (gda.date).

The value mirrors Gramps' date model — modifier (regular/before/after/about/
range/span/textonly) + quality (regular/estimated/calculated) + partial date
parts — so Gramps-side tooling can consume it without translation. A month or
day of 0 means "unknown", exactly as in Gramps datevals.

Stored shape (schema 1):
    {"schema": 1, "modifier": "about", "quality": "estimated",
     "start": {"year": 1920, "month": 0, "day": 0}, "stop": null,
     "text": "", "display": "estimated about 1920", "sort": "1920-07-02"}

`display` is regenerated on every save (user `text` wins when set); `sort` is
a derived ISO date for client-side ordering — never authoritative.

MODIFIERS/QUALITIES tuple order doubles as the Gramps integer code for each
value (modules/sync_immich.py keeps the explicit numeric maps; a test pins
the two in sync) — reorder these and the Gramps mapping breaks.
"""

from __future__ import annotations

import calendar
from datetime import date

MODIFIERS = ("regular", "before", "after", "about", "range", "span", "textonly")
QUALITIES = ("regular", "estimated", "calculated")

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

_QUALITY_PREFIX = {"regular": "", "estimated": "estimated ", "calculated": "calculated "}
_RANGE_MODIFIERS = ("range", "span")


class DateError(ValueError):
    pass


def _int_field(raw: dict, key: str, name: str) -> int:
    value = raw.get(key)
    if value is None or value == "":
        return 0
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise DateError(f"{name}: {key} must be a whole number")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise DateError(f"{name}: year/month/day must be numbers") from exc


def _part(raw: object, name: str) -> dict:
    if not isinstance(raw, dict):
        raise DateError(f"{name}: a year is required")
    year = _int_field(raw, "year", name)
    month = _int_field(raw, "month", name)
    day = _int_field(raw, "day", name)
    if not 1 <= year <= 9999:
        raise DateError(f"{name}: a year (1-9999) is required")
    if not 0 <= month <= 12:
        raise DateError(f"{name}: month must be blank or 1-12")
    if month == 0:
        if day != 0:
            raise DateError(f"{name}: a day needs a month")
    else:
        last = calendar.monthrange(year, month)[1]
        if not 0 <= day <= last:
            raise DateError(f"{name}: day must be blank or 1-{last}")
    return {"year": year, "month": month, "day": day}


def _bounds(part: dict) -> tuple[date, date]:
    y, m, d = part["year"], part["month"], part["day"]
    if m == 0:
        return date(y, 1, 1), date(y, 12, 31)
    if d == 0:
        return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
    return date(y, m, d), date(y, m, d)


def _sort_key(modifier: str, start: dict | None, stop: dict | None) -> str | None:
    if start is None:
        return None
    lo, hi = _bounds(start)
    if modifier == "before":
        return lo.isoformat()
    if modifier == "after":
        return hi.isoformat()
    if modifier in _RANGE_MODIFIERS and stop is not None:
        hi = _bounds(stop)[1]
    return (lo + (hi - lo) / 2).isoformat()


def _part_text(part: dict) -> str:
    y, m, d = part["year"], part["month"], part["day"]
    if m == 0:
        return str(y)
    if d == 0:
        return f"{MONTHS[m - 1]} {y}"
    return f"{d} {MONTHS[m - 1]} {y}"


def _humanize(modifier: str, quality: str, start: dict | None, stop: dict | None) -> str:
    if modifier == "textonly" or start is None:
        return ""
    s = _part_text(start)
    if modifier in _RANGE_MODIFIERS and stop is not None:
        e = _part_text(stop)
        body = f"between {s} and {e}" if modifier == "range" else f"from {s} to {e}"
    else:
        body = {"regular": s, "about": f"about {s}", "before": f"before {s}", "after": f"after {s}"}[modifier]
    return (_QUALITY_PREFIX[quality] + body).strip()


def validate(payload: object) -> dict:
    """Normalize a date payload from the editor; raise DateError when invalid."""
    if not isinstance(payload, dict):
        raise DateError("expected a date object")
    modifier = payload.get("modifier") or "regular"
    quality = payload.get("quality") or "regular"
    if modifier not in MODIFIERS:
        raise DateError(f"unknown modifier: {modifier!r}")
    if quality not in QUALITIES:
        raise DateError(f"unknown quality: {quality!r}")

    text = str(payload.get("text") or "").strip()
    start = stop = None
    if modifier == "textonly":
        if not text:
            raise DateError("a text-only date needs text")
    else:
        start = _part(payload.get("start"), "start")
        if modifier in _RANGE_MODIFIERS:
            stop = _part(payload.get("stop"), "end")
            if _bounds(stop)[1] < _bounds(start)[0]:
                raise DateError("the end of the range precedes its start")

    return {
        "schema": 1,
        "modifier": modifier,
        "quality": quality,
        "start": start,
        "stop": stop,
        "text": text,
        "display": text or _humanize(modifier, quality, start, stop),
        "sort": _sort_key(modifier, start, stop),
    }
