from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Mapping

from ..core import ids
from ..core.clients import GrampsClient
from ..core.clients.gramps import note_obj

NOTE_TYPE = "Withdrawn codes"
REASON_MAX = 1000

IN_USE, WITHDRAWN = "in use", "withdrawn"
ATTENTION = "attention"
STATUSES = (IN_USE, WITHDRAWN)

SOURCE_ATTRS = {"Immich ID": "immich", "Paperless ID": "paperless"}
LINE_RE = re.compile(r"^([A-Z0-9]{4,6})\s+(\d{4}-\d{2}-\d{2})(?:\s+(.*))?$")


class CodeError(Exception):

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class Urls:
    gramps: str = ""
    paperless: str = ""
    immich: str = ""


def normalize(raw: str | None) -> str:
    return re.sub(r"[\s-]+", "", raw or "").upper()


def status_filter(raw: str | None) -> str | None:
    text = " ".join((raw or "").lower().replace("_", " ").replace("-", " ").split())
    if not text or text == "all":
        return None
    if text in ("attention", "needs attention"):
        return ATTENTION
    if text in STATUSES:
        return text
    raise ValueError(f"unknown status {raw!r}")


# ---- the withdrawn-codes note

def parse_note(text: str | None) -> dict[str, dict]:
    """{code: {withdrawn, reason}} from the note's lines; lines that are not a code entry are skipped"""
    out: dict[str, dict] = {}
    for line in (text or "").splitlines():
        m = LINE_RE.match(line.strip())
        if m:
            out[m.group(1)] = {"withdrawn": m.group(2), "reason": (m.group(3) or "").strip()}
    return out


def note_line(code: str, when: str, reason: str) -> str:
    return f"{code} {when} {reason}".rstrip()


async def withdrawn_note(gramps: GrampsClient) -> dict | None:
    notes = await gramps.find_notes(NOTE_TYPE)
    return notes[0] if notes else None


async def withdrawn(gramps: GrampsClient) -> dict[str, dict]:
    note = await withdrawn_note(gramps)
    return parse_note(((note or {}).get("text") or {}).get("string")) if note else {}


async def withdraw(gramps: GrampsClient, raw: str | None, reason: str | None,
                   when: str | None = None) -> str:
    """Add a code to the note; a withdrawn code is never issued again"""
    code = normalize(raw)
    if not code:
        raise CodeError(400, "No code given.")
    text = " ".join((reason or "").split())
    if not text:
        raise CodeError(400, "Give a reason.")
    if len(text) > REASON_MAX:
        raise CodeError(400, "The reason is too long.")
    note = await withdrawn_note(gramps)
    current = ((note or {}).get("text") or {}).get("string") or ""
    entry = parse_note(current).get(code)
    if entry:
        raise CodeError(409, f"{code} was already withdrawn on {entry['withdrawn']}: {entry['reason']}")
    line = note_line(code, when or date.today().isoformat(), text)
    body = f"{current.rstrip()}\n{line}" if current.strip() else line
    if note:
        await gramps.update_note(note["handle"], note_obj(note["handle"], note["gramps_id"], body, NOTE_TYPE))
    else:
        await gramps.create_note(note_obj(ids.generate_handle(), await gramps.next_note_id(), body, NOTE_TYPE))
    return code


# ---- new codes

def check_code(raw: str | None, live: Iterable[str], withdrawn: Mapping[str, dict],
               paperless: Mapping[str, list] | None = None) -> str:
    """A code written down by hand, normalized, if a media may take it"""
    code = normalize(raw)
    if not code:
        raise CodeError(400, "Type the code as written.")
    bad = sorted({ch for ch in code if ch not in ids.CHARSET})
    if bad:
        raise CodeError(400, f"{code} contains {', '.join(bad)}. "
                             "Codes use A-Z and 2-9 but avoid ambiguous characters I, L, O, 0 and 1.")
    if len(code) != 6:
        raise CodeError(400, f"{code} has {len(code)} characters.")
    why = ids.guard_reason(code)
    if why:
        raise CodeError(400, f"{code} {why}, so it is never used as a code.")
    entry = withdrawn.get(code)
    if entry:
        raise CodeError(409, f"{code} was withdrawn on {entry['withdrawn']}: {entry['reason']}.")
    if code in set(live):
        raise CodeError(409, f"{code} is already the ID of a Gramps media object.")
    docs = (paperless or {}).get(code)
    if docs:
        raise CodeError(409, f"{code} is already in the Gramps ID field of Paperless document "
                             f"{', '.join(str(d) for d in docs)}.")
    return code


# ---- the list

def source_of(media: dict) -> tuple[str | None, str | None]:
    """('immich' | 'paperless', id) from the media's attributes"""
    for a in media.get("attribute_list") or []:
        system = SOURCE_ATTRS.get(a.get("type"))
        value = (a.get("value") or "").strip()
        if system and value:
            return system, value
    return None, None


def _iso(change) -> str | None:
    try:
        return datetime.fromtimestamp(int(change), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError):
        return None


def _row(code: str, media: dict | None, entry: dict | None, urls: Urls,
         documents: set[str] | None) -> dict:
    system, source_id = source_of(media) if media else (None, None)
    status = WITHDRAWN if entry else IN_USE
    paperless = [source_id] if system == "paperless" else []
    immich = [source_id] if system == "immich" else []
    attention = None
    if entry and media:
        attention = "Withdrawn but still in Gramps"
    elif media and documents is not None and any(d not in documents for d in paperless):
        attention = "Deleted from Paperless"
    mime = (media or {}).get("mime") or ""
    kind = ("image" if system == "immich" else "document" if system == "paperless"
            else "image" if mime.startswith("image/") else None)
    return {
        "code": code,
        "status": status,
        "attention": attention,
        "type": kind,
        "title": (media or {}).get("desc") or None,
        "gramps": media is not None,
        "gramps_url": f"{urls.gramps}/media/{code}" if urls.gramps and media else None,
        "paperless": [{"id": d, "url": f"{urls.paperless}/documents/{d}/details" if urls.paperless else None}
                      for d in paperless],
        "immich": [{"id": a, "url": f"{urls.immich}/photos/{a}" if urls.immich else None} for a in immich],
        "updated": _iso(media.get("change")) if media else entry["withdrawn"],
        "withdrawn": entry["withdrawn"] if entry else None,
        "withdrawn_reason": entry["reason"] if entry else None,
    }


def rows(media: list[dict], withdrawn: Mapping[str, dict], urls: Urls = Urls(),
         documents: set[str] | None = None, only: Iterable[str] | None = None) -> list[dict]:
    """Every code, newest first: the Gramps media with a code as id, plus the withdrawn note's entries"""
    by_code = {m["gramps_id"]: m for m in media
               if m.get("gramps_id") and ids.MANUAL_ID_RE.match(m["gramps_id"])}
    codes = set(by_code) | set(withdrawn)
    if only is not None:
        codes &= {normalize(c) for c in only}
    out = [_row(c, by_code.get(c), withdrawn.get(c), urls, documents) for c in codes]
    out.sort(key=lambda r: r["code"])
    out.sort(key=lambda r: (r["updated"] or "")[:19], reverse=True)
    return out


def search(items: list[dict], q: str | None) -> list[dict]:
    text = " ".join((q or "").split()).casefold()
    if not text:
        return items
    code_q = normalize(text)

    def hit(r: dict) -> bool:
        if code_q and code_q in r["code"]:
            return True
        hay = [r["title"], r["withdrawn_reason"],
               *(d["id"] for d in r["paperless"]), *(a["id"] for a in r["immich"])]
        return any(text in str(v).casefold() for v in hay if v)

    return [r for r in items if hit(r)]


def matches(r: dict, wanted: str | None) -> bool:
    if wanted is None:
        return True
    if wanted == ATTENTION:
        return bool(r["attention"])
    return r["status"] == wanted


def counts(items: list[dict]) -> dict:
    out = {"all": len(items), **{s: 0 for s in STATUSES}, ATTENTION: 0}
    for r in items:
        out[r["status"]] += 1
        if r["attention"]:
            out[ATTENTION] += 1
    return out
