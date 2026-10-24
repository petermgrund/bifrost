from __future__ import annotations

import re
from datetime import date as _date

MODIFIERS = {"regular": 0, "before": 1, "after": 2, "about": 3, "range": 4, "span": 5, "textonly": 6}
QUALITIES = {"regular": 0, "estimated": 1, "calculated": 2}
_MODIFIER_NAMES = {v: k for k, v in MODIFIERS.items()}
_QUALITY_NAMES = {v: k for k, v in QUALITIES.items()}
PRECISIONS = ("exact", "month", "year")
FORM_MODIFIERS = ("regular", "about", "before", "after", "decade", "span")
RANGES = ("decade", "span")
SPAN_MAX = 999
EMPTY_DATE = {"_class": "Date", "dateval": [0, 0, 0, False], "modifier": 0, "quality": 0, "text": ""}
_DATE_RE = re.compile(r"^\s*(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?\s*$")


def plain_date(day: int, month: int, year: int, modifier: int = 0, quality: int = 0) -> dict:
    return {"_class": "Date", "dateval": [day, month, year, False],
            "modifier": modifier, "quality": quality, "text": ""}


def range_date(start: int, stop: int, quality: int = 0) -> dict:
    return {"_class": "Date", "dateval": [0, 0, start, False, 0, 0, stop, False],
            "modifier": MODIFIERS["range"], "quality": quality, "text": ""}


def year_range(modifier: str, year: int, span: tuple[int, int] | None) -> tuple[int, int]:
    """First and last year of a decade (1945 -> 1940, 1949) or a span around the year"""
    if modifier == "decade":
        return year - year % 10, year - year % 10 + 9
    minus, plus = span or (0, 0)
    return year - minus, year + plus


def _ymd(day: int, month: int, year: int) -> str:
    if day == 0 and month == 0:
        return f"{year}"
    if day == 0:
        return f"{year}-{month:02d}"
    return f"{year}-{month:02d}-{day:02d}"


def format_gramps_date(date_obj: dict | None) -> str:
    if not date_obj:
        return "(none)"
    dv = date_obj.get("dateval") or []
    if len(dv) < 3:
        return "(none)"
    day, month, year = dv[0], dv[1], dv[2]
    if year == 0 and month == 0 and day == 0:
        return "(none)"
    qual = {1: "Est. ", 2: "Calc. "}.get(date_obj.get("quality", 0), "")
    modifier = date_obj.get("modifier", 0)
    if modifier in (4, 5) and len(dv) >= 7:
        first, last = _ymd(day, month, year), _ymd(dv[4], dv[5], dv[6])
        return f"{qual}Between {first} and {last}" if modifier == 4 else f"{qual}From {first} to {last}"
    mod = {1: "Before ", 2: "After ", 3: "About "}.get(modifier, "")
    return f"{qual}{mod}{_ymd(day, month, year)}"


def gramps_date_text(d: dict | None) -> str:
    """A Gramps date as Gramps Web shows it, text-only dates included"""
    if not d:
        return ""
    if d.get("modifier") == MODIFIERS["textonly"] or format_gramps_date(d) == "(none)":
        return (d.get("text") or "").strip()
    return format_gramps_date(d)


def dates_equal(a: dict | None, b: dict | None) -> bool:
    """Only the fields Bifrost writes"""
    if not a and not b:
        return True
    if not a or not b:
        return False
    return ((a.get("dateval") or []) == (b.get("dateval") or [])
            and (a.get("modifier") or 0) == (b.get("modifier") or 0)
            and (a.get("quality") or 0) == (b.get("quality") or 0))


def parse_date_value(text: str) -> tuple[str, str] | None:
    """'1923', '1923-06' or '1923-06-15' -> (ISO date, implied precision)"""
    m = _DATE_RE.match(text or "")
    if not m:
        return None
    y, mo, d = m.group(1), m.group(2), m.group(3)
    try:
        value = _date(int(y), int(mo or 1), int(d or 1)).isoformat()
    except ValueError:
        return None
    return value, ("exact" if d else "month" if mo else "year")


def effective_precision(form: dict) -> str:
    """About dates fall back to the month; decades and spans are years"""
    if form.get("modifier") in RANGES:
        return "year"
    precision = form.get("precision") or "exact"
    if form.get("modifier") == "about" and precision == "exact":
        return "month"
    return precision


def gramps_date(form: dict) -> dict:
    """The editor's date fields as a Gramps Date"""
    y, m, d = (int(x) for x in form["value"].split("-"))
    quality = QUALITIES[form.get("quality") or "regular"]
    if form.get("modifier") in RANGES:
        span = (form.get("minus") or 0, form.get("plus") or 0)
        return range_date(*year_range(form["modifier"], y, span), quality)
    precision = effective_precision(form)
    if precision == "year":
        d, m = 0, 0
    elif precision == "month":
        d = 0
    return plain_date(d, m, y, MODIFIERS[form.get("modifier") or "regular"], quality)


def date_display(form: dict | None) -> str:
    return format_gramps_date(gramps_date(form)) if form else ""


def date_from_gramps(d: dict | None) -> tuple[dict | None, str | None]:
    """(editor form, None) for a Gramps date the form can hold, (None, its text) for one it cannot,
    (None, None) for no date"""
    dv = list((d or {}).get("dateval") or [])
    text = gramps_date_text(d)
    if not text:
        return None, None
    modifier, quality = d.get("modifier") or 0, d.get("quality") or 0
    if (len(dv) < 4 or dv[3] or d.get("calendar") or d.get("newyear") or dv[2] <= 0
            or modifier not in (0, 1, 2, 3, 4) or quality not in _QUALITY_NAMES):
        return None, text
    form = {"quality": _QUALITY_NAMES[quality]}
    if modifier == 4:
        if len(dv) < 8 or dv[7] or any(dv[i] for i in (0, 1, 4, 5)) or not 0 <= dv[6] - dv[2] <= SPAN_MAX:
            return None, text
        start, stop = dv[2], dv[6]
        form.update({"value": f"{start:04d}-01-01", "precision": "year"})
        if start % 10 == 0 and stop == start + 9:
            form["modifier"] = "decade"
        else:
            form.update({"modifier": "span", "minus": 0, "plus": stop - start})
    else:
        day, month, year = dv[0], dv[1], dv[2]
        name = _MODIFIER_NAMES[modifier]
        if name == "about" and day:
            return None, text
        try:
            value = _date(year, month or 1, day or 1).isoformat()
        except ValueError:
            return None, text
        form.update({"value": value, "modifier": name,
                     "precision": "exact" if day else "month" if month else "year"})
    form["display"] = date_display(form)
    return form, None
