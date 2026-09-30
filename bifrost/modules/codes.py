"""GDA codes: the Object ID ledger behind the Codes page

A code (Object ID) has 6 characters from ids.CHARSET and is the archive's only
citable identifier. It names an item (a photo with its back, a document, a
saved file) or a group described as one (an album, a bundle of letters, a
box's worth of loose prints). A code is never reused, changed or deleted:
reserved_ids holds reservations, code_pencilings each time a code was penciled
on its item (crossed_at = erased or written wrong), minted_media what sync
created in Gramps, withdrawn_codes the retired ones, objects the description
of any code, code_descriptions each change to it, code_notes its notes (moved
to the photo's notes once an Immich asset takes the code) and code_instances
the links and text naming other places it lives. Status is derived, never
stored.
Locations (B2.C3.F1, S1) are where a thing is kept, not codes.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from ..core import ids

KINDS = ("item", "group")
MAX_MINT = 20
NOTE_MAX = 1000
NOTES_MAX = 10000
LOCATION_MAX = 100
REASON_MAX = 1000
INSTANCE_MAX = 2000

RESERVED, PENCILED, IN_USE, WITHDRAWN = "reserved", "penciled", "in use", "withdrawn"
ATTENTION = "attention"
STATUSES = (RESERVED, PENCILED, IN_USE, WITHDRAWN)

CSV_COLUMNS = (
    "code", "status", "needs_attention", "type", "kind", "note", "title", "notes", "part_of",
    "location",
    "items_in_group", "in_gramps", "gramps_url", "paperless_docs", "paperless_urls",
    "immich_assets", "immich_urls", "scans", "instances", "created", "penciled", "minted",
    "withdrawn", "withdrawn_reason",
)

_LOCATION_RE = re.compile(
    r"^([BS])([1-9][0-9]*)(?:\.?C([1-9][0-9]*))?(?:\.?F([1-9][0-9]*))?$", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


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


def _now() -> str:
    # naive UTC, like the ledger's other rows (written in a UTC container) and
    # migration 15's seed, so dates sort the same wherever bifrost runs
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def normalize(raw: str | None) -> str:
    """' phkn-3d ' -> 'PHKN3D'"""
    return re.sub(r"[\s-]+", "", raw or "").upper()


def normalize_location(raw: str | None) -> str | None:
    """'b2c3f1' -> 'B2.C3.F1'; other text is kept as typed, whitespace tidied"""
    text = " ".join((raw or "").split())
    if not text:
        return None
    if len(text) > LOCATION_MAX:
        raise CodeError(400, f"The location is too long (at most {LOCATION_MAX} characters).")
    m = _LOCATION_RE.match(text.replace(" ", ""))
    if m:
        place, number, compartment, folder = m.groups()
        return (f"{place.upper()}{number}" + (f".C{compartment}" if compartment else "")
                + (f".F{folder}" if folder else ""))
    return text


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
        f"unknown status {raw!r}: use reserved, penciled, in use, withdrawn or attention")


# ---- reading the ledger

def _load(conn: sqlite3.Connection) -> dict:
    led = {
        "reserved": {r["gramps_id"]: r for r in conn.execute("SELECT * FROM reserved_ids")},
        "minted": {r["gramps_id"]: r for r in conn.execute("SELECT * FROM minted_media")},
        "objects": {r["object_id"]: r for r in conn.execute("SELECT * FROM objects")},
        "withdrawn": {r["code"]: r for r in conn.execute("SELECT * FROM withdrawn_codes")},
        "scans": {},
        "versions": {},
        "children": {},
        "descriptions": {},
        "notes": {},
        "instances": {},
        "pencilings": {},
    }
    for r in conn.execute("SELECT * FROM code_descriptions ORDER BY changed_at, rowid"):
        led["descriptions"].setdefault(r["code"], []).append(r)
    for r in conn.execute("SELECT * FROM code_notes ORDER BY changed_at, rowid"):
        led["notes"].setdefault(r["code"], []).append(r)
    for r in conn.execute("SELECT * FROM code_pencilings ORDER BY id"):
        led["pencilings"].setdefault(r["code"], []).append(r)
    for r in conn.execute("SELECT * FROM code_instances ORDER BY id"):
        led["instances"].setdefault(r["code"], []).append(r)
    for r in conn.execute(
            "SELECT scan_no, object_id FROM scan_register "
            "WHERE object_id IS NOT NULL ORDER BY scan_no"):
        led["scans"].setdefault(r["object_id"], []).append(r["scan_no"])
    for r in conn.execute(
            "SELECT paperless_id, gramps_id FROM doc_versions "
            "WHERE gramps_id IS NOT NULL ORDER BY paperless_id"):
        led["versions"].setdefault(r["gramps_id"], []).append(str(r["paperless_id"]))
    for r in led["objects"].values():
        if r["parent_id"]:
            led["children"][r["parent_id"]] = led["children"].get(r["parent_id"], 0) + 1
    return led


def _in_ledger(led: dict, code: str) -> bool:
    return any(code in led[k] for k in ("reserved", "minted", "objects", "withdrawn", "scans"))


def _penciled(led: dict, code: str) -> bool:
    return any(not p["crossed_at"] for p in led["pencilings"].get(code, []))


def _status(led: dict, code: str, live: set[str] | None) -> str:
    res = led["reserved"].get(code)
    if code in led["withdrawn"]:
        return WITHDRAWN
    if code in led["minted"] or (res is not None and res["minted_at"]) \
            or (live is not None and code in live):
        return IN_USE
    if _penciled(led, code):
        return PENCILED
    return RESERVED


def _record(led: dict, code: str) -> str | None:
    """Where a code's digital record lives, like 'Immich' or 'Paperless document 16'"""
    minted = led["minted"].get(code)
    if minted is not None:
        return ("Immich" if minted["source_system"] == "immich"
                else f"Paperless document {minted['source_id']}")
    docs = led["versions"].get(code)
    return f"Paperless document {docs[0]}" if docs else None


def _type(led: dict, code: str) -> str | None:
    """'image' for a code minted from Immich, 'document' for one in Paperless"""
    minted = led["minted"].get(code)
    if minted is not None:
        return "image" if minted["source_system"] == "immich" else "document"
    return "document" if led["versions"].get(code) else None


def _history(led: dict, code: str) -> list[dict]:
    """What happened to a code, oldest first"""
    res = led["reserved"].get(code)
    minted = led["minted"].get(code)
    gone = led["withdrawn"].get(code)
    minted_at = (minted["minted_at"] if minted else None) or (res["minted_at"] if res else None)
    events = []
    if res is not None and res["created_at"][:19] != (minted_at or "")[:19]:
        events.append((res["created_at"], "Created", res["note"]))
    for d in led["descriptions"].get(code, []):
        events.append((d["changed_at"],
                       "Description changed" if d["note"] else "Description cleared", d["note"]))
    for n in led["notes"].get(code, []):
        events.append((n["changed_at"], "Notes changed" if n["text"] else "Notes cleared",
                       n["text"] or None))
    instances = led["instances"].get(code, [])
    events += [(i["added_at"], "Instance added", i["value"]) for i in instances]
    events += [(i["removed_at"], "Instance removed", i["value"])
               for i in instances if i["removed_at"]]
    pencilings = list(enumerate(led["pencilings"].get(code, []), start=1))
    events += [(p["penciled_at"], f"Penciled #{n}", None) for n, p in pencilings]
    events += [(p["crossed_at"], f"Penciling #{n} crossed out", None)
               for n, p in pencilings if p["crossed_at"]]
    if minted_at:
        events.append((minted_at, f"Minted from {_record(led, code)}" if minted else "Minted", None))
    if gone is not None:
        events.append((gone["withdrawn_at"], "Withdrawn", gone["reason"]))
    events.sort(key=lambda e: e[0][:19])
    return [{"at": at, "what": what, "detail": detail} for at, what, detail in events]


def _notes(led: dict, code: str) -> str:
    """A code's notes; a code with an Immich or Paperless record keeps none here"""
    log = led["notes"].get(code)
    return "" if _record(led, code) or not log else log[-1]["text"]


def notes_of(conn: sqlite3.Connection, code: str) -> str:
    """The notes written for a code in the Codes page"""
    row = conn.execute("SELECT text FROM code_notes WHERE code=? ORDER BY changed_at DESC, "
                       "rowid DESC LIMIT 1", (normalize(code),)).fetchone()
    return row["text"] if row else ""


def _instances(led: dict, code: str, row: dict) -> list[dict]:
    """Where a code's object lives: its digital records, then links and text added by hand"""
    out = [{"id": None, "where": "Immich", "text": f"Asset {a['id'][:8]}", "url": a["url"]}
           for a in row["immich"]]
    out += [{"id": None, "where": "Paperless", "text": f"Document {d['id']}", "url": d["url"]}
            for d in row["paperless"]]
    if row["gramps"]:
        out.append({"id": None, "where": "Gramps", "text": f"Media {code}",
                    "url": row["gramps_url"]})
    out += [{"id": None, "where": "Scan", "text": s, "url": None} for s in row["scans"]]
    for i in led["instances"].get(code, []):
        if not i["removed_at"]:
            url = i["kind"] == "url"
            out.append({"id": i["id"], "where": "Link" if url else "Text", "text": i["value"],
                        "url": i["value"] if url else None})
    return out


def _row(led: dict, code: str, live: set[str] | None, urls: Urls,
         titles: Mapping[str, str]) -> dict:
    res = led["reserved"].get(code)
    minted = led["minted"].get(code)
    obj = led["objects"].get(code)
    gone = led["withdrawn"].get(code)
    pencilings = led["pencilings"].get(code, [])
    status = _status(led, code, live)
    in_gramps = None if live is None else code in live
    history = _history(led, code)

    attention = None
    if status == IN_USE:
        if not _in_ledger(led, code):
            attention = "In Gramps, but not in bifrost's ledger"
        elif in_gramps is False:
            attention = "Minted, but its Gramps media is gone"

    paperless = [minted["source_id"]] if minted and minted["source_system"] == "paperless" else []
    paperless += [d for d in led["versions"].get(code, []) if d not in paperless]
    immich = [minted["source_id"]] if minted and minted["source_system"] == "immich" else []

    if obj is not None:
        kind, note = obj["kind"], obj["note"]
    else:
        kind, note = "item", res["note"] if res is not None else None
    notes = _notes(led, code)

    row = {
        "code": code,
        "status": status,
        "attention": attention,
        "in_ledger": _in_ledger(led, code),
        "type": _type(led, code),
        "kind": kind,
        "note": note,
        "title": titles.get(code) or (minted["title"] if minted else None),
        "notes": notes,
        "parent": obj["parent_id"] if obj is not None else None,
        "location": obj["location"] if obj is not None else None,
        "children": led["children"].get(code, 0),
        "gramps": in_gramps,
        "gramps_url": f"{urls.gramps}/media/{code}" if urls.gramps and in_gramps else None,
        "paperless": [{"id": d, "url": f"{urls.paperless}/documents/{d}/details"
                       if urls.paperless else None} for d in paperless],
        "immich": [{"id": a, "url": f"{urls.immich}/photos/{a}" if urls.immich else None}
                   for a in immich],
        "scans": led["scans"].get(code, []),
        "created": res["created_at"] if res is not None else None,
        "penciled": next((p["penciled_at"] for p in reversed(pencilings)
                          if not p["crossed_at"]), None),
        "pencilings": [{"id": p["id"], "n": n, "at": p["penciled_at"], "crossed": p["crossed_at"]}
                       for n, p in enumerate(pencilings, start=1)],
        "minted": (minted["minted_at"] if minted else None) or (res["minted_at"] if res else None),
        "withdrawn": gone["withdrawn_at"] if gone is not None else None,
        "withdrawn_reason": gone["reason"] if gone is not None else None,
        "updated": history[-1]["at"] if history else None,
        "history": history,
    }
    row["instances"] = _instances(led, code, row)
    return row


def rows(conn: sqlite3.Connection, live: set[str] | None, urls: Urls = Urls(),
         only: Iterable[str] | None = None,
         titles: Mapping[str, str] | None = None) -> list[dict]:
    """Every code, newest first. live=None means Gramps could not be read, so
    'in use' rests on the ledger alone and missing media can't be flagged"""
    titles = titles or {}
    led = _load(conn)
    codes = set().union(*(led[k] for k in ("reserved", "minted", "objects", "withdrawn", "scans")))
    if live is not None:
        codes |= {c for c in live if ids.MANUAL_ID_RE.match(c)}
    if only is not None:
        codes &= {normalize(c) for c in only}
    out = [_row(led, c, live, urls, titles) for c in codes]
    # birth date (reserved or minted) newest first; codes with none, like the
    # retired 4-character ones, go last
    out.sort(key=lambda r: r["code"])
    out.sort(key=lambda r: (r["created"] or r["minted"] or "")[:19], reverse=True)
    return out


def search(items: list[dict], q: str | None) -> list[dict]:
    text = " ".join((q or "").split()).casefold()
    if not text:
        return items
    code_q = normalize(text)

    def hit(r: dict) -> bool:
        if code_q and code_q in r["code"]:
            return True
        hay = [r["note"], r["title"], r["notes"], r["location"], r["parent"], r["withdrawn_reason"],
               *(d["id"] for d in r["paperless"]), *(a["id"] for a in r["immich"]), *r["scans"],
               *(i["text"] for i in r["instances"] if i["id"])]
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

def _require_known(led: dict, code: str) -> None:
    if not code:
        raise CodeError(400, "No code given.")
    if not _in_ledger(led, code):
        raise CodeError(404, f"{code} is not in the ledger.")


def _kind(raw: str | None) -> str:
    kind = (raw or "").strip().lower()
    if kind not in KINDS:
        raise CodeError(400, "The kind must be item or group.")
    return kind


def _note(raw: str | None) -> str | None:
    note = " ".join((raw or "").split())
    if len(note) > NOTE_MAX:
        raise CodeError(400, f"The note is too long (at most {NOTE_MAX} characters).")
    return note or None


def _parent(led: dict, raw: str | None, code: str | None = None) -> str | None:
    """A parent must be a code already in the ledger whose kind is group"""
    parent = normalize(raw)
    if not parent:
        return None
    if parent == code:
        raise CodeError(400, f"{code} can't be part of itself.")
    if not _in_ledger(led, parent):
        raise CodeError(400, f"Part of: {parent} is not in the ledger.")
    if parent in led["withdrawn"]:
        raise CodeError(400, f"Part of: {parent} is withdrawn.")
    obj = led["objects"].get(parent)
    if obj is None or obj["kind"] != "group":
        raise CodeError(400, f"Part of: {parent} is not a group. Edit it and make it a group first.")
    seen = {parent}
    up = obj["parent_id"]
    while up and up not in seen:
        if up == code:
            raise CodeError(400, f"{code} can't be part of {parent}, which is already part of {code}.")
        seen.add(up)
        above = led["objects"].get(up)
        up = above["parent_id"] if above is not None else None
    return parent


def _description(led: dict, *, kind: str | None, note: str | None, parent: str | None,
                 location: str | None, code: str | None = None) -> dict:
    return {
        "kind": _kind(kind),
        "note": _note(note),
        "parent_id": _parent(led, parent, code),
        "location": normalize_location(location),
    }


def check_description(conn: sqlite3.Connection, *, kind: str | None, note: str | None,
                      parent: str | None = None, location: str | None = None) -> None:
    """Validate a new code's description before anything is fetched or written"""
    _description(_load(conn), kind=kind, note=note, parent=parent, location=location)


def _where_seen(led: dict, code: str, live: set[str],
                paperless: Mapping[str, list]) -> str | None:
    minted = led["minted"].get(code)
    if minted is not None:
        source = ("Paperless document" if minted["source_system"] == "paperless"
                  else "Immich asset")
        return (f"{code} is already in use: minted from {source} {minted['source_id']} "
                f"on {(minted['minted_at'] or '')[:10]}.")
    res = led["reserved"].get(code)
    if res is not None:
        state = "penciled" if _penciled(led, code) else "reserved"
        return f"{code} is already in the ledger: {state} since {(res['created_at'] or '')[:10]}."
    if code in led["objects"]:
        return f"{code} is already in the ledger."
    if code in led["scans"]:
        return f"{code} is already in the scan register ({', '.join(led['scans'][code])})."
    if code in live:
        return f"{code} is already the ID of a Gramps media object."
    if code in paperless:
        docs = ", ".join(str(d) for d in paperless[code])
        return f"{code} is already in the Gramps ID field of Paperless document {docs}."
    return None


def check_new(conn: sqlite3.Connection, raw: str | None, live: Iterable[str] = (),
              paperless: Mapping[str, list] | None = None) -> str:
    """A code Peter wrote down by hand, normalized, if it may enter the ledger"""
    led = _load(conn)
    code = normalize(raw)
    if not code:
        raise CodeError(400, "Type the code as it is written.")
    gone = led["withdrawn"].get(code)
    if gone is not None:
        raise CodeError(409, f"{code} was withdrawn on {gone['withdrawn_at'][:10]}: "
                             f"{gone['reason']}. A withdrawn code is never used again.")
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

def _insert(conn: sqlite3.Connection, codes: list[str], desc: dict) -> None:
    now = _now()
    with conn:
        for code in codes:
            conn.execute(
                "INSERT INTO reserved_ids (gramps_id, created_at, note) VALUES (?, ?, ?)",
                (code, now, desc["note"]))
            conn.execute(
                "INSERT INTO objects (object_id, kind, parent_id, location, note, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (code, desc["kind"], desc["parent_id"], desc["location"], desc["note"], now))


def mint(conn: sqlite3.Connection, *, kind: str | None, note: str | None,
         parent: str | None = None, location: str | None = None, count: int = 1,
         live: Iterable[str] = (), paperless: Iterable[str] = ()) -> list[str]:
    """Reserve `count` new codes, excluding every code ever seen and the guarded shapes"""
    if not isinstance(count, int) or not 1 <= count <= MAX_MINT:
        raise CodeError(400, f"Mint between 1 and {MAX_MINT} codes at a time.")
    desc = _description(_load(conn), kind=kind, note=note, parent=parent, location=location)
    existing = ids.all_ids_ever_seen(conn, live, paperless)
    codes = [ids.generate_gramps_id(existing) for _ in range(count)]
    _insert(conn, codes, desc)
    return codes


def claim(conn: sqlite3.Connection, raw: str | None, *, kind: str | None, note: str | None,
          parent: str | None = None, location: str | None = None,
          live: Iterable[str] = (), paperless: Mapping[str, list] | None = None) -> str:
    """Register a code that was written down before bifrost issued it"""
    code = check_new(conn, raw, live, paperless)
    desc = _description(_load(conn), kind=kind, note=note, parent=parent, location=location,
                        code=code)
    _insert(conn, [code], desc)
    return code


def mark_penciled(conn: sqlite3.Connection, raw: str | None) -> str:
    """Record one more penciling of the code on its item"""
    led = _load(conn)
    code = normalize(raw)
    _require_known(led, code)
    if code in led["withdrawn"]:
        raise CodeError(409, f"{code} is withdrawn, so it is not marked penciled.")
    if _type(led, code) == "document":
        raise CodeError(409, f"{code} is a document, and documents are not penciled.")
    with conn:
        conn.execute("INSERT INTO code_pencilings (code, penciled_at) VALUES (?, ?)",
                     (code, _now()))
    return code


def cross_out_penciling(conn: sqlite3.Connection, raw: str | None, penciling_id: int) -> str:
    """Cross out one penciling, erased or written wrong; the others stand"""
    led = _load(conn)
    code = normalize(raw)
    _require_known(led, code)
    p = next((p for p in led["pencilings"].get(code, []) if p["id"] == penciling_id), None)
    if p is None:
        raise CodeError(404, f"{code} has no such penciling.")
    if p["crossed_at"]:
        raise CodeError(409, f"That penciling of {code} is already crossed out.")
    with conn:
        conn.execute("UPDATE code_pencilings SET crossed_at=? WHERE id=?", (_now(), penciling_id))
    return code


def withdraw(conn: sqlite3.Connection, raw: str | None, reason: str | None) -> str:
    """Retire a code for good. Nothing is deleted; the code is never issued again"""
    led = _load(conn)
    code = normalize(raw)
    text = " ".join((reason or "").split())
    if not text:
        raise CodeError(400, "Give a reason. The ledger keeps it with the code for good.")
    if len(text) > REASON_MAX:
        raise CodeError(400, f"The reason is too long (at most {REASON_MAX} characters).")
    gone = led["withdrawn"].get(code)
    if gone is not None:
        raise CodeError(409, f"{code} was already withdrawn on {gone['withdrawn_at'][:10]}: "
                             f"{gone['reason']}")
    _require_known(led, code)
    with conn:
        conn.execute(
            "INSERT INTO withdrawn_codes (code, withdrawn_at, reason) VALUES (?, ?, ?)",
            (code, _now(), text))
    return code


def _notes_text(raw: str | None) -> str:
    text = (raw or "").replace("\r\n", "\n").strip()
    if len(text) > NOTES_MAX:
        raise CodeError(400, f"The notes are too long (at most {NOTES_MAX} characters).")
    return text


def update(conn: sqlite3.Connection, raw: str | None, changes: Mapping) -> str:
    """Change a code's description (note, kind, part of, location) or notes; only given keys change"""
    led = _load(conn)
    code = normalize(raw)
    _require_known(led, code)
    obj = led["objects"].get(code)
    res = led["reserved"].get(code)
    current = {
        "kind": obj["kind"] if obj is not None else "item",
        "note": obj["note"] if obj is not None else (res["note"] if res is not None else None),
        "parent_id": obj["parent_id"] if obj is not None else None,
        "location": obj["location"] if obj is not None else None,
    }
    new = dict(current)
    if "kind" in changes:
        new["kind"] = _kind(changes["kind"])
        children = led["children"].get(code, 0)
        if new["kind"] != "group" and children:
            raise CodeError(409, f"{code} has {children} code{'s' if children != 1 else ''} "
                                 "under it. Move them to another group first.")
    if "note" in changes:
        new["note"] = _note(changes["note"])
        record = _record(led, code)
        if record and new["note"] != current["note"]:
            raise CodeError(409, f"{code} is described in {record}. Change it there.")
    if "parent" in changes:
        new["parent_id"] = _parent(led, changes["parent"], code)
    if "location" in changes:
        new["location"] = normalize_location(changes["location"])
    notes = None
    if "notes" in changes:
        notes = _notes_text(changes["notes"])
        record = _record(led, code)
        if notes == _notes(led, code):
            notes = None
        elif record:
            raise CodeError(409, f"{code} is in {record}, so its notes go there.")
    if new == current and notes is None:
        return code
    now = _now()
    with conn:
        if new != current:
            conn.execute(
                "INSERT INTO objects (object_id, kind, parent_id, location, note, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(object_id) DO UPDATE SET "
                "kind=excluded.kind, parent_id=excluded.parent_id, location=excluded.location, "
                "note=excluded.note, updated_at=excluded.updated_at",
                (code, new["kind"], new["parent_id"], new["location"], new["note"], now))
        if new["note"] != current["note"]:
            conn.execute("INSERT INTO code_descriptions (code, changed_at, note) VALUES (?, ?, ?)",
                         (code, now, new["note"]))
        if notes is not None:
            conn.execute("INSERT INTO code_notes (code, changed_at, text) VALUES (?, ?, ?)",
                         (code, now, notes))
    return code


def open_codes(conn: sqlite3.Connection, live: set[str]) -> list[dict]:
    """Reserved and penciled codes an Immich asset can take, penciled first"""
    items = [r for r in rows(conn, live) if r["status"] in (RESERVED, PENCILED) and r["created"]]
    items.sort(key=lambda r: r["status"] != PENCILED)
    return [{k: r[k] for k in ("code", "status", "note", "notes", "penciled", "created")}
            for r in items]


def add_instance(conn: sqlite3.Connection, raw: str | None, value: str | None) -> str:
    """List a link to another place the code's object lives"""
    led = _load(conn)
    code = normalize(raw)
    _require_known(led, code)
    if code in led["withdrawn"]:
        raise CodeError(409, f"{code} is withdrawn, so nothing is added to it.")
    url = (value or "").strip()
    if not _URL_RE.match(url):
        raise CodeError(400, "That is not a link starting with http:// or https://.")
    if len(url) > INSTANCE_MAX:
        raise CodeError(400, f"That is too long (at most {INSTANCE_MAX} characters).")
    if any(i["value"] == url and not i["removed_at"] for i in led["instances"].get(code, [])):
        raise CodeError(409, f"{code} already lists that.")
    with conn:
        conn.execute(
            "INSERT INTO code_instances (code, kind, value, added_at) VALUES (?, 'url', ?, ?)",
            (code, url, _now()))
    return code


def remove_instance(conn: sqlite3.Connection, raw: str | None, instance_id: int) -> str:
    """Take a link off a code; its history keeps it"""
    led = _load(conn)
    code = normalize(raw)
    _require_known(led, code)
    with conn:
        cur = conn.execute(
            "UPDATE code_instances SET removed_at=? WHERE id=? AND code=? AND removed_at IS NULL",
            (_now(), instance_id, code))
    if not cur.rowcount:
        raise CodeError(404, f"{code} does not list that.")
    return code


# ---- export

def to_csv(items: list[dict]) -> str:
    """Every column of every code; the BOM makes Excel read it as UTF-8 (å ä ö)"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for r in items:
        writer.writerow([
            r["code"], r["status"], r["attention"] or "", r["type"] or "", r["kind"],
            r["note"] or "", r["title"] or "", r["notes"], r["parent"] or "", r["location"] or "",
            r["children"] or "",
            {True: "yes", False: "no", None: "unknown"}[r["gramps"]], r["gramps_url"] or "",
            " ".join(d["id"] for d in r["paperless"]),
            " ".join(d["url"] for d in r["paperless"] if d["url"]),
            " ".join(a["id"] for a in r["immich"]),
            " ".join(a["url"] for a in r["immich"] if a["url"]),
            " ".join(r["scans"]), " | ".join(i["text"] for i in r["instances"] if i["id"]),
            r["created"] or "", " ".join(p["at"] for p in r["pencilings"] if not p["crossed"]),
            r["minted"] or "", r["withdrawn"] or "", r["withdrawn_reason"] or "",
        ])
    return "\ufeff" + buf.getvalue()
