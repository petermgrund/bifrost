from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from ..core import dates, ids

SOURCE_ATTRS = {"Immich ID": "immich", "Paperless ID": "paperless"}
MERGED_ATTR = "Merged Gramps ID"


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


def new_id(codes: bool, taken: set[str]) -> str:
    """The Gramps ID of a new media object: a code, or Gramps' own next O number"""
    if codes:
        return ids.generate_gramps_id(taken)
    gid = ids.next_sequential_id("O", taken)
    taken.add(gid)
    return gid


def check_code(raw: str | None, live: Iterable[str], paperless: Mapping[str, list] | None = None) -> str:
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
    if code in set(live):
        raise CodeError(409, f"{code} is already the ID of a Gramps media object.")
    docs = (paperless or {}).get(code)
    if docs:
        raise CodeError(409, f"{code} is already in the Gramps ID field of Paperless document "
                             f"{', '.join(str(d) for d in docs)}.")
    return code


def sources_of(media: dict) -> list[tuple[str, str]]:
    """('immich' | 'paperless', id) for every source the media's attributes name"""
    out = []
    for a in media.get("attribute_list") or []:
        system = SOURCE_ATTRS.get(a.get("type"))
        value = (a.get("value") or "").strip()
        if system and value and (system, value) not in out:
            out.append((system, value))
    return out


def merged_ids(media: dict) -> list[str]:
    """The Gramps IDs of the media objects merged into this one"""
    return [a["value"] for a in media.get("attribute_list") or []
            if a.get("type") == MERGED_ATTR and a.get("value")]


def _row(media: dict, urls: Urls, documents: set[str] | None) -> dict:
    code = media["gramps_id"]
    sources = sources_of(media)
    paperless = [sid for system, sid in sources if system == "paperless"]
    immich = [sid for system, sid in sources if system == "immich"]
    attention = None
    if documents is not None and any(d not in documents for d in paperless):
        attention = "Deleted from Paperless"
    mime = media.get("mime") or ""
    kind = ("document" if paperless else "image" if immich or mime.startswith("image/") else None)
    return {
        "code": code,
        "attention": attention,
        "type": kind,
        "title": media.get("desc") or None,
        "gramps_url": f"{urls.gramps}/media/{code}" if urls.gramps else None,
        "paperless": [{"id": d, "url": f"{urls.paperless}/documents/{d}/details" if urls.paperless else None}
                      for d in paperless],
        "immich": [{"id": a, "url": f"{urls.immich}/photos/{a}" if urls.immich else None} for a in immich],
        "merged": merged_ids(media),
        "date": dates.gramps_date_text(media.get("date")) or None,
    }


def rows(media: list[dict], urls: Urls = Urls(), documents: set[str] | None = None) -> list[dict]:
    """Last changed first: the Gramps media that came from Paperless or Immich"""
    found = [m for m in media if m.get("gramps_id") and sources_of(m)]
    found.sort(key=lambda m: m["gramps_id"])
    found.sort(key=lambda m: m.get("change") or 0, reverse=True)
    return [_row(m, urls, documents) for m in found]
