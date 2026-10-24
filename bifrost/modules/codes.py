"""The Codes ledger: every code Bifrost issued, claimed or withdrew, and the media it stands for"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable, Mapping

from ..core import ids
from ..core.db import now

MAX_MINT = 20
REASON_MAX = 1000

RESERVED, IN_USE, WITHDRAWN = "reserved", "in use", "withdrawn"
ATTENTION = "attention"
STATUSES = (RESERVED, IN_USE, WITHDRAWN)

CSV_COLUMNS = (
    "code", "status", "needs_attention", "type", "title", "in_gramps", "gramps_url",
    "paperless_docs", "paperless_urls", "immich_assets", "immich_urls",
    "created", "minted", "withdrawn", "withdrawn_reason", "superseded_by",
)


class CodeError(Exception):
    """A refused ledger change, with the HTTP status that fits it"""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class Urls:
    """Public base URLs for the 'used in' links; empty means no link"""
    gramps: str = ""
    paperless: str = ""
    immich: str = ""


def normalize(raw: str | None) -> str:
    """' phkn-3d ' -> 'PHKN3D'"""
    return re.sub(r"[\s-]+", "", raw or "").upper()


def status_filter(raw: str | None) -> str | None:
    """'in_use' -> 'in use', 'needs attention' -> 'attention', '' -> None"""
    text = " ".join((raw or "").lower().replace("_", " ").replace("-", " ").split())
    if not text or text == "all":
        return None
    if text in ("attention", "needs attention"):
        return ATTENTION
    if text in STATUSES:
        return text
    raise ValueError(
        f"unknown status {raw!r}: use reserved, in use, withdrawn or attention")


# ---- reading the ledger

def _load(conn: sqlite3.Connection) -> dict:
    led = {
        "codes": {r["gramps_id"]: r for r in conn.execute("SELECT * FROM minted_media")},
        "versions": {},
        "supersedes": {},
    }
    for code, r in led["codes"].items():
        if r["superseded_by"]:
            led["supersedes"].setdefault(r["superseded_by"], []).append(code)
    for r in conn.execute(
            "SELECT paperless_id, gramps_id FROM doc_versions "
            "WHERE gramps_id IS NOT NULL ORDER BY paperless_id"):
        led["versions"].setdefault(r["gramps_id"], []).append(str(r["paperless_id"]))
    return led


def _status(led: dict, code: str, live: set[str] | None) -> str:
    r = led["codes"].get(code)
    if r is not None and r["withdrawn_at"]:
        return WITHDRAWN
    if (r is not None and r["source_system"]) or (live is not None and code in live):
        return IN_USE
    return RESERVED


def _record(led: dict, code: str) -> str | None:
    """Where a code's digital record lives, like 'Immich' or 'Paperless document 16'"""
    r = led["codes"].get(code)
    if r is not None and r["source_system"]:
        return "Immich" if r["source_system"] == "immich" else f"Paperless document {r['source_id']}"
    docs = led["versions"].get(code)
    return f"Paperless document {docs[0]}" if docs else None


def _type(led: dict, code: str) -> str | None:
    """'image' for a code minted from Immich, 'document' for one in Paperless"""
    r = led["codes"].get(code)
    if r is not None and r["source_system"]:
        return "image" if r["source_system"] == "immich" else "document"
    return "document" if led["versions"].get(code) else None


def _history(led: dict, code: str) -> list[dict]:
    """What happened to a code, oldest first"""
    r = led["codes"].get(code)
    if r is None:
        return []
    events = []
    if (r["created_at"] or "")[:19] != (r["minted_at"] or "")[:19]:
        events.append((r["created_at"], "Created", None))
    if r["minted_at"]:
        events.append((r["minted_at"], f"Minted from {_record(led, code)}"
                       if r["source_system"] else "Minted", None))
    if r["withdrawn_at"]:
        events.append((r["withdrawn_at"], "Withdrawn", r["withdrawn_reason"]))
    events.sort(key=lambda e: e[0][:19])
    return [{"at": at, "what": what, "detail": detail} for at, what, detail in events]


def _deletable(led: dict, code: str, live: set[str] | None) -> bool:
    """Only reserved: never minted, withdrawn or in Gramps"""
    r = led["codes"].get(code)
    return (r is not None and not r["source_system"] and not r["withdrawn_at"]
            and code not in led["versions"] and code not in (live or ()))


def _row(led: dict, code: str, live: set[str] | None, urls: Urls,
         titles: Mapping[str, str], documents: set[str] | None) -> dict:
    r = led["codes"].get(code)
    status = _status(led, code, live)
    in_gramps = None if live is None else code in live
    history = _history(led, code)

    paperless = [r["source_id"]] if r is not None and r["source_system"] == "paperless" else []
    paperless += [d for d in led["versions"].get(code, []) if d not in paperless]
    deleted = [] if documents is None else [d for d in paperless if d not in documents]
    paperless = [d for d in paperless if d not in deleted]
    immich = [r["source_id"]] if r is not None and r["source_system"] == "immich" else []

    attention = None
    if status == IN_USE:
        missing = [name for name, gone in (("Gramps", in_gramps is False), ("Paperless", deleted))
                   if gone]
        if r is None:
            attention = "In Gramps, but not in bifrost's ledger"
        elif missing:
            attention = f"Deleted from {' and '.join(missing)}"
    elif status == WITHDRAWN and in_gramps:
        attention = "Withdrawn, but still in Gramps"

    return {
        "code": code,
        "status": status,
        "attention": attention,
        "in_ledger": r is not None,
        "type": _type(led, code),
        "title": titles.get(code),
        "gramps": in_gramps,
        "gramps_url": f"{urls.gramps}/media/{code}" if urls.gramps and in_gramps else None,
        "paperless": [{"id": d, "url": f"{urls.paperless}/documents/{d}/details"
                       if urls.paperless else None} for d in paperless],
        "immich": [{"id": a, "url": f"{urls.immich}/photos/{a}" if urls.immich else None}
                   for a in immich],
        "created": r["created_at"] if r is not None else None,
        "minted": r["minted_at"] if r is not None else None,
        "withdrawn": r["withdrawn_at"] if r is not None else None,
        "withdrawn_reason": r["withdrawn_reason"] if r is not None else None,
        "superseded_by": r["superseded_by"] if r is not None else None,
        "supersedes": sorted(led["supersedes"].get(code, [])),
        "deletable": _deletable(led, code, live),
        "updated": history[-1]["at"] if history else None,
        "history": history,
    }


def rows(conn: sqlite3.Connection, live: set[str] | None, urls: Urls = Urls(),
         only: Iterable[str] | None = None,
         titles: Mapping[str, str] | None = None,
         documents: set[str] | None = None) -> list[dict]:
    """Every code, newest first. live=None means Gramps could not be read, so
    'in use' rests on the ledger alone and missing media can't be flagged;
    documents=None likewise for Paperless"""
    titles = titles or {}
    led = _load(conn)
    codes = set(led["codes"])
    if live is not None:
        codes |= {c for c in live if ids.MANUAL_ID_RE.match(c)}
    if only is not None:
        codes &= {normalize(c) for c in only}
    out = [_row(led, c, live, urls, titles, documents) for c in codes]
    # birth date newest first; codes with none, like the retired 4-character ones, go last
    out.sort(key=lambda r: r["code"])
    out.sort(key=lambda r: (r["created"] or "")[:19], reverse=True)
    return out


def search(items: list[dict], q: str | None) -> list[dict]:
    text = " ".join((q or "").split()).casefold()
    if not text:
        return items
    code_q = normalize(text)

    def hit(r: dict) -> bool:
        if code_q and code_q in r["code"]:
            return True
        hay = [r["title"], r["withdrawn_reason"], r["superseded_by"],
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


# ---- validation

def _require_known(led: dict, code: str) -> sqlite3.Row:
    if not code:
        raise CodeError(400, "No code given.")
    r = led["codes"].get(code)
    if r is None:
        raise CodeError(404, f"{code} is not in the ledger.")
    return r


def _where_seen(led: dict, code: str, live: set[str],
                paperless: Mapping[str, list]) -> str | None:
    r = led["codes"].get(code)
    if r is not None and r["source_system"]:
        source = "Paperless document" if r["source_system"] == "paperless" else "Immich asset"
        return (f"{code} is already in use: minted from {source} {r['source_id']} "
                f"on {(r['minted_at'] or '')[:10]}.")
    if r is not None:
        return f"{code} is already in the ledger: reserved since {(r['created_at'] or '')[:10]}."
    if code in live:
        return f"{code} is already the ID of a Gramps media object."
    if code in paperless:
        docs = ", ".join(str(d) for d in paperless[code])
        return f"{code} is already in the Gramps ID field of Paperless document {docs}."
    return None


def check_new(conn: sqlite3.Connection, raw: str | None, live: Iterable[str] = (),
              paperless: Mapping[str, list] | None = None) -> str:
    """A code written down by hand, normalized, if it may enter the ledger"""
    led = _load(conn)
    code = normalize(raw)
    if not code:
        raise CodeError(400, "Type the code as it is written.")
    r = led["codes"].get(code)
    if r is not None and r["withdrawn_at"]:
        raise CodeError(409, f"{code} was withdrawn on {r['withdrawn_at'][:10]}: "
                             f"{r['withdrawn_reason']}. A withdrawn code is never used again.")
    bad = sorted({ch for ch in code if ch not in ids.CHARSET})
    if bad:
        raise CodeError(400, f"{code} contains {', '.join(bad)}, which no code uses. "
                             "Codes use A-Z and 2-9, never I, L, O, 0 or 1.")
    if len(code) != 6:
        raise CodeError(400, f"{code} has {len(code)} characters; a code has exactly 6.")
    why = ids.guard_reason(code)
    if why:
        raise CodeError(400, f"{code} {why}, so it is never used as a code.")
    live = set(live)
    paperless = paperless or {}
    seen = _where_seen(led, code, live, paperless)
    if seen:
        raise CodeError(409, seen)
    if code in ids.all_ids_ever_seen(conn, live, paperless):
        raise CodeError(409, f"{code} has been used before.")
    return code


# ---- writing the ledger

def _reserve(conn: sqlite3.Connection, codes: list[str]) -> None:
    when = now()
    with conn:
        conn.executemany("INSERT INTO minted_media (gramps_id, created_at) VALUES (?, ?)",
                         [(code, when) for code in codes])


def mint(conn: sqlite3.Connection, count: int = 1, live: Iterable[str] = (),
         paperless: Iterable[str] = ()) -> list[str]:
    """Reserve `count` new codes, excluding every code ever seen and the guarded shapes"""
    if not isinstance(count, int) or not 1 <= count <= MAX_MINT:
        raise CodeError(400, f"Mint between 1 and {MAX_MINT} codes at a time.")
    existing = ids.all_ids_ever_seen(conn, live, paperless)
    codes = [ids.generate_gramps_id(existing) for _ in range(count)]
    _reserve(conn, codes)
    return codes


def claim(conn: sqlite3.Connection, raw: str | None, live: Iterable[str] = (),
          paperless: Mapping[str, list] | None = None) -> str:
    """Register a code that was written down before bifrost issued it"""
    code = check_new(conn, raw, live, paperless)
    _reserve(conn, [code])
    return code


def _superseding(led: dict, code: str, raw: str | None) -> str | None:
    """A code in the ledger, other than this one and not withdrawn, that takes its place"""
    other = normalize(raw)
    if not other:
        return None
    if other == code:
        raise CodeError(400, f"{code} can't supersede itself.")
    r = led["codes"].get(other)
    if r is None:
        raise CodeError(400, f"{other} is not in the ledger.")
    if r["withdrawn_at"]:
        raise CodeError(400, f"{other} is withdrawn.")
    return other


def withdraw(conn: sqlite3.Connection, raw: str | None, reason: str | None,
             superseded_by: str | None = None) -> str:
    """Retire a code for good, optionally naming the code that takes its place"""
    led = _load(conn)
    code = normalize(raw)
    text = " ".join((reason or "").split())
    if not text:
        raise CodeError(400, "Give a reason. The ledger keeps it with the code for good.")
    if len(text) > REASON_MAX:
        raise CodeError(400, f"The reason is too long (at most {REASON_MAX} characters).")
    r = _require_known(led, code)
    if r["withdrawn_at"]:
        raise CodeError(409, f"{code} was already withdrawn on {r['withdrawn_at'][:10]}: "
                             f"{r['withdrawn_reason']}")
    other = _superseding(led, code, superseded_by)
    with conn:
        conn.execute(
            "UPDATE minted_media SET withdrawn_at=?, withdrawn_reason=?, superseded_by=? "
            "WHERE gramps_id=?", (now(), text, other, code))
    return code


def supersede(conn: sqlite3.Connection, raw: str | None, superseded_by: str | None) -> str:
    """Name, change or clear the code that takes a withdrawn code's place"""
    led = _load(conn)
    code = normalize(raw)
    r = _require_known(led, code)
    if not r["withdrawn_at"]:
        raise CodeError(409, f"{code} is not withdrawn, so nothing supersedes it.")
    other = _superseding(led, code, superseded_by)
    if other != r["superseded_by"]:
        with conn:
            conn.execute("UPDATE minted_media SET superseded_by=? WHERE gramps_id=?", (other, code))
    return code


def delete(conn: sqlite3.Connection, raw: str | None, live: Iterable[str] = (),
           paperless: Mapping[str, list] | None = None) -> str:
    """Remove a reservation nothing has used yet; the code may be issued again"""
    led = _load(conn)
    code = normalize(raw)
    _require_known(led, code)
    if not _deletable(led, code, set(live)) or code in (paperless or {}):
        raise CodeError(409, f"{code} has been used, so it can only be withdrawn.")
    if led["supersedes"].get(code):
        raise CodeError(409, f"{code} supersedes {', '.join(led['supersedes'][code])}.")
    with conn:
        conn.execute("DELETE FROM minted_media WHERE gramps_id=?", (code,))
    return code


def open_codes(conn: sqlite3.Connection, live: set[str]) -> list[dict]:
    """Reserved codes an Immich asset can take"""
    return [{k: r[k] for k in ("code", "status", "created")}
            for r in rows(conn, live) if r["status"] == RESERVED and r["in_ledger"]]


# ---- export

def to_csv(items: list[dict]) -> str:
    """Every column of every code; the BOM makes Excel read it as UTF-8 (å ä ö)"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for r in items:
        writer.writerow([
            r["code"], r["status"], r["attention"] or "", r["type"] or "", r["title"] or "",
            {True: "yes", False: "no", None: "unknown"}[r["gramps"]], r["gramps_url"] or "",
            " ".join(d["id"] for d in r["paperless"]),
            " ".join(d["url"] for d in r["paperless"] if d["url"]),
            " ".join(a["id"] for a in r["immich"]),
            " ".join(a["url"] for a in r["immich"] if a["url"]),
            r["created"] or "", r["minted"] or "", r["withdrawn"] or "",
            r["withdrawn_reason"] or "", r["superseded_by"] or "",
        ])
    return "﻿" + buf.getvalue()
