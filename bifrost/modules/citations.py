"""Gramps Sources and Citations made in the citations wizard, and the Paperless scan filed with them"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from datetime import datetime, timezone

from ..core.clients import GrampsClient, PaperlessClient
from ..core.config import SyncPaperlessConfig
from ..core.ids import generate_handle, next_sequential_id
from .ancestry_links import media_ref
from .codes import normalize

CONFIDENCE = ("Very Low", "Low", "Normal", "High", "Very High")
WIZARD_ATTRIBUTES = ("Subject", "Record", "Household", "Which entry", "Source says", "Evidence", "Record type", "Guide")
TAG_COLOR = "#7b5ea7"
DATE_MEANING = "date meaning"
REFERENCE_NOTES = re.compile(r"FIRST REFERENCE NOTE:\s*(?P<frn>.*?)\s*SHORT REFERENCE NOTE:\s*(?P<srn>.*?)\s*$", re.S)
KINDS = {"person": "people", "family": "families", "event": "events"}
SEARCH_LIMITS = (("person", 8), ("family", 4), ("event", 6))
PROFILE = {"profile": "self", "keys": "handle,gramps_id,profile"}


class CitationError(Exception):
    """A refused create, with the HTTP status that fits it"""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


def note_text(frn: str, srn: str) -> str:
    return f"FIRST REFERENCE NOTE:\n{frn.strip()}\n\nSHORT REFERENCE NOTE:\n{srn.strip()}"


def reference_notes(text: str) -> tuple[str, str]:
    """The FRN and SRN of a citation note laid out as note_text lays them out, or blanks"""
    m = REFERENCE_NOTES.search(text or "")
    return (m["frn"], m["srn"]) if m else ("", "")


def citation_attributes(existing: list[dict] | None, pairs) -> list[dict]:
    """The citation's own attributes kept, the wizard's (A7) replaced by the given pairs"""
    kept = [a for a in existing or [] if (a.get("type") or "") not in WIZARD_ATTRIBUTES]
    made = [{"_class": "SrcAttribute", "type": str(t), "value": _text(v), "private": False}
            for t, v in pairs or [] if str(t) in WIZARD_ATTRIBUTES and _text(v)]
    return kept + made


async def tag_for(gramps: GrampsClient, name: str, objs: list[dict], now: int) -> str:
    """The handle of the Gramps tag with this name; a new tag joins the objects about to be created"""
    handle = await gramps.get_tag_handle(name)
    if handle:
        return handle
    handle = generate_handle()
    objs.append({"_class": "Tag", "handle": handle, "name": name, "color": TAG_COLOR, "priority": 0, "change": now})
    return handle


def gramps_id_of(cfg: SyncPaperlessConfig, doc: dict) -> str:
    """The document's Gramps ID, set once it is synced to Gramps"""
    field = cfg.gramps_id_field_id
    value = PaperlessClient.custom_field_value(doc, field) if field else None
    return normalize(str(value)) if value else ""


def date_meaning_field(fields: list[dict]) -> dict | None:
    return next((f for f in fields if (f.get("name") or "").strip().lower() == DATE_MEANING
                 and f.get("data_type") == "select"), None)


def remember(conn: sqlite3.Connection, handle: str, record_type: str, inputs: dict) -> None:
    """Keep the wizard inputs a Source was cited with, to fill them in when it is picked again"""
    with conn:
        conn.execute(
            "INSERT INTO citation_sources (handle, record_type, inputs, used_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(handle) DO UPDATE SET record_type=excluded.record_type, inputs=excluded.inputs, "
            "used_at=excluded.used_at",
            (handle, record_type, json.dumps(inputs, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat(timespec="seconds")))


def remembered(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["handle"]: {"type": r["record_type"], "inputs": json.loads(r["inputs"]), "used_at": r["used_at"]}
            for r in conn.execute("SELECT handle, record_type, inputs, used_at FROM citation_sources")}


def keep_draft(conn: sqlite3.Connection, citation_handle: str, record_type: str, draft: dict) -> None:
    """Keep the wizard draft a citation was made from, to start the next citation on its media from it"""
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO citation_drafts (citation_handle, record_type, draft, created_at) "
            "VALUES (?, ?, ?, ?)",
            (citation_handle, record_type, json.dumps(draft, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat(timespec="seconds")))


def kept_drafts(conn: sqlite3.Connection, handles) -> dict[str, dict]:
    """{citation handle: {"type", "draft"}} for the given citations the wizard made"""
    handles = list(handles)
    if not handles:
        return {}
    rows = conn.execute("SELECT citation_handle, record_type, draft FROM citation_drafts "
                        f"WHERE citation_handle IN ({', '.join('?' * len(handles))})", handles)
    return {r["citation_handle"]: {"type": r["record_type"], "draft": json.loads(r["draft"])} for r in rows}


def _year(date) -> str:
    m = re.search(r"\d{3,4}", str(date or ""))
    return m.group(0) if m else ""


def _name(prof: dict) -> str:
    parts = (str(prof.get(k) or "").strip() for k in ("name_given", "name_surname", "name_suffix"))
    return " ".join(p for p in parts if p) or prof.get("name_display") or ""


def row(kind: str, obj: dict) -> dict:
    """How a person, family or event shows in the attach list, from its Gramps profile"""
    prof = obj.get("profile") or {}
    gid = obj.get("gramps_id") or ""
    if kind == "person":
        years = [_year((prof.get(k) or {}).get("date")) for k in ("birth", "death")]
        name = short = _name(prof) or gid
        detail = "–".join(years) if any(years) else ""
    elif kind == "family":
        couple = [_name(prof.get(k) or {}) for k in ("father", "mother")]
        name = short = " & ".join(n for n in couple if n) or prof.get("family_surname") or gid
        detail = prof.get("relationship") or ""
    else:
        short = prof.get("type") or gid
        name = prof.get("summary") or short
        detail = " · ".join(p for p in (prof.get("date"), prof.get("place_name")) if p)
    return {"kind": kind, "handle": obj["handle"], "gramps_id": gid, "name": name, "short": short, "detail": detail}


async def rows(gramps: GrampsClient, pairs) -> list[dict]:
    """Attach-list rows for (kind, handle) pairs, in order, skipping repeats and handles Gramps no longer has"""
    pairs = list(dict.fromkeys(pairs))
    objs = await asyncio.gather(*(gramps.find_object(KINDS[k], h, **PROFILE) for k, h in pairs))
    return [row(k, o) for (k, _), o in zip(pairs, objs) if o]


async def find(gramps: GrampsClient, q: str) -> list[dict]:
    """People, then families, then events with every typed word, through Gramps' full-text search"""
    words = re.findall(r"\w+", q)
    if not words:
        return []
    query = " ".join(f"{w}*" for w in words)
    found = await asyncio.gather(*(gramps.search(query, kind, limit) for kind, limit in SEARCH_LIMITS))
    return [row(kind, hit["object"]) for (kind, _), hits in zip(SEARCH_LIMITS, found)
            for hit in hits if hit.get("object")]


async def related(gramps: GrampsClient, kind: str, handle: str) -> list[dict]:
    """A person's events and families with their events, or a family's events and people, with depth"""
    if kind == "person":
        person = await gramps.find_object("people", handle, keys="event_ref_list,family_list,parent_family_list")
        if not person:
            return []
        events, families = await asyncio.gather(
            rows(gramps, [("event", r["ref"]) for r in person.get("event_ref_list") or []]),
            _families(gramps, (person.get("family_list") or []) + (person.get("parent_family_list") or [])))
        return [{**r, "depth": 1} for r in events] + families
    family = await gramps.find_object(
        "families", handle, keys="event_ref_list,father_handle,mother_handle,child_ref_list")
    if not family:
        return []
    people = [h for h in (family.get("father_handle"), family.get("mother_handle")) if h]
    people += [r["ref"] for r in family.get("child_ref_list") or []]
    found = await rows(gramps, [("event", r["ref"]) for r in family.get("event_ref_list") or []]
                       + [("person", h) for h in people])
    return [{**r, "depth": 1} for r in found]


async def _families(gramps: GrampsClient, handles: list[str]) -> list[dict]:
    fams = await asyncio.gather(*(gramps.find_object("families", h, profile="self",
                                                     keys="handle,gramps_id,profile,event_ref_list")
                                  for h in dict.fromkeys(handles)))
    fams = [f for f in fams if f]
    events = await asyncio.gather(*(rows(gramps, [("event", r["ref"]) for r in f.get("event_ref_list") or []])
                                    for f in fams))
    return [r for f, evs in zip(fams, events)
            for r in ({**row("family", f), "depth": 1}, *({**e, "depth": 2} for e in evs))]


async def context(gramps: GrampsClient, paperless: PaperlessClient, conn: sqlite3.Connection) -> dict:
    """The Sources and Repositories in Gramps, and the Paperless names a scan is filed under"""
    sources, repos, doctypes, people, fields = await asyncio.gather(
        gramps._paged("/sources/", keys="handle,gramps_id,title,author,abbrev,pubinfo,reporef_list"),
        gramps._paged("/repositories/", keys="handle,gramps_id,name,type"),
        paperless.document_types(), paperless.correspondents(), paperless.custom_fields())
    names = {r["handle"]: r.get("name") or "" for r in repos}
    meaning = date_meaning_field(fields)
    memory = remembered(conn)
    return {
        "sources": sorted((
            {"handle": s["handle"], "gramps_id": s.get("gramps_id") or "", "title": s.get("title") or "",
             "author": s.get("author") or "", "abbrev": s.get("abbrev") or "", "pubinfo": s.get("pubinfo") or "",
             "repositories": [{"name": names.get(r.get("ref"), ""), "call_number": r.get("call_number") or ""}
                              for r in s.get("reporef_list") or []],
             "remembered": memory.get(s["handle"])}
            for s in sources), key=lambda s: s["title"].lower()),
        "repositories": sorted((
            {"handle": r["handle"], "gramps_id": r.get("gramps_id") or "", "name": r.get("name") or "",
             "type": str(r.get("type") or "")} for r in repos), key=lambda r: r["name"].lower()),
        "document_types": [{"id": d["id"], "name": d["name"]} for d in doctypes],
        "correspondents": [{"id": c["id"], "name": c["name"]} for c in people],
        "date_meaning": ({"field": meaning["id"],
                          "options": (meaning.get("extra_data") or {}).get("select_options") or []}
                         if meaning else None),
    }


async def document(gramps: GrampsClient, paperless: PaperlessClient, cfg: SyncPaperlessConfig,
                   doc_id: int, conn: sqlite3.Connection) -> dict:
    """The Paperless document, its Gramps media with its citations newest first, and the records both are attached to"""
    doc, fields = await asyncio.gather(paperless.get_document(doc_id), paperless.custom_fields())
    pid = gramps_id_of(cfg, doc)
    if not pid:
        raise CitationError(403, f"Paperless document #{doc_id} isn't synced to Gramps")
    media = await gramps.get_media_by_gramps_id(pid)
    cited, suggestions = [], []
    if media:
        links = await gramps.get_media_backlinks(media["handle"])
        cits = await asyncio.gather(*(gramps.get_object("citations", h, backlinks="true")
                                      for h in links.get("citation") or []))
        handles = sorted({c.get("source_handle") for c in cits if c.get("source_handle")})
        srcs = dict(zip(handles, await asyncio.gather(*(gramps.get_object("sources", h) for h in handles))))
        kept = kept_drafts(conn, (c["handle"] for c in cits))
        note_handles = sorted({h for c in cits for h in c.get("note_list") or []})
        notes = dict(zip(note_handles, await asyncio.gather(*(gramps.get_object("notes", h) for h in note_handles))))

        def notes_of(c: dict) -> tuple[str, str]:
            for h in c.get("note_list") or []:
                frn, srn = reference_notes(((notes.get(h) or {}).get("text") or {}).get("string") or "")
                if frn or srn:
                    return frn, srn
            return "", ""

        for c in cits:
            frn, srn = notes_of(c)
            cited.append({"handle": c["handle"], "gramps_id": c.get("gramps_id") or "", "page": c.get("page") or "",
                          "confidence": c.get("confidence"), "change": c.get("change") or 0,
                          "source_handle": c.get("source_handle") or "",
                          "source": (srcs.get(c.get("source_handle")) or {}).get("title") or "",
                          "frn": frn, "srn": srn, "draft": kept.get(c["handle"])})
        cited.sort(key=lambda c: (-c["change"], c["gramps_id"]))
        back = {c["handle"]: c.get("backlinks") or {} for c in cits}
        order = ("event", "person", "family")
        suggestions = await rows(gramps, [(k, h) for c in cited for k in order for h in back[c["handle"]].get(k) or []]
                                 + [(k, h) for k in order for h in links.get(k) or []])
    meaning = date_meaning_field(fields)
    url = cfg.source_url_field_id
    return {
        "id": doc_id, "title": doc.get("title") or f"#{doc_id}", "pid": pid,
        "created": doc.get("created") or "",
        "source_url": (paperless.custom_field_value(doc, url) or "") if url else "",
        "document_type": doc.get("document_type"), "correspondent": doc.get("correspondent"),
        "date_meaning": paperless.custom_field_value(doc, meaning["id"]) if meaning else None,
        "media": {"handle": media["handle"], "gramps_id": media.get("gramps_id") or pid} if media else None,
        "citations": cited,
        "suggestions": suggestions,
    }


def _text(value) -> str:
    return " ".join(str(value or "").split())


async def _next_ids(gramps: GrampsClient, kinds: list[tuple[str, str]]) -> list[str]:
    taken = await asyncio.gather(*(gramps._paged(f"/{path}/", keys="gramps_id") for path, _ in kinds))
    return [next_sequential_id(prefix, {i["gramps_id"] for i in items if i.get("gramps_id")})
            for (_, prefix), items in zip(kinds, taken)]


async def create(gramps: GrampsClient, paperless: PaperlessClient, cfg: SyncPaperlessConfig,
                 doc_id: int, source: dict, citation: dict, scan: dict | None, attach: list[dict] | None = None) -> dict:
    """Make the Source when new and the Citation with its note on the document's media, attach it, file the scan"""
    picks = list(dict.fromkeys((p.get("kind"), p.get("handle")) for p in attach or []))
    if any(kind not in KINDS or not handle for kind, handle in picks):
        raise CitationError(400, "A citation attaches only to people, families and events")
    page, frn, srn = (citation.get(k, "").strip() for k in ("page", "frn", "srn"))
    confidence = citation.get("confidence")
    if confidence not in CONFIDENCE:
        raise CitationError(400, "Choose a confidence level")
    if not (page and frn and srn):
        raise CitationError(400, "The citation needs a page, an FRN, and an SRN")
    repo_handle = (source.get("repository") or {}).get("handle")
    if source.get("handle"):
        src = await gramps.get_object("sources", source["handle"])
        repo_handle = None
    elif not _text(source.get("title")):
        raise CitationError(400, "The new Source needs a title")
    if repo_handle:
        await gramps.get_object("repositories", repo_handle)
    call = _text(source.get("call_number"))
    if call and not repo_handle and not source.get("handle"):
        raise CitationError(400, "A call number needs a Repository")

    doc = await paperless.get_document(doc_id)
    pid = gramps_id_of(cfg, doc)
    if not pid:
        raise CitationError(403, f"Paperless document #{doc_id} isn't synced to Gramps")
    media = await gramps.get_media_by_gramps_id(pid)
    if not media:
        raise CitationError(409, f"Gramps has no media {pid}")
    found = await asyncio.gather(*(gramps.find_object(KINDS[k], h, keys="handle,gramps_id") for k, h in picks))
    if gone := next((k for (k, _), o in zip(picks, found) if not o), None):
        raise CitationError(409, f"A picked {gone} is no longer in Gramps")
    targets = [(k, h, o.get("gramps_id") or h) for (k, h), o in zip(picks, found)]

    kinds = ([] if source.get("handle") else [("sources", "S")]) + [("notes", "N"), ("citations", "C")]
    minted = dict(zip((prefix for _, prefix in kinds), await _next_ids(gramps, kinds)))
    now = int(datetime.now(timezone.utc).timestamp())
    objs, made = [], []

    if source.get("handle"):
        src_handle, src_id, src_title = src["handle"], src.get("gramps_id") or "", src.get("title") or ""
    else:
        src_handle, src_id, src_title = generate_handle(), minted["S"], _text(source["title"])
        reporefs = [{"_class": "RepoRef", "ref": repo_handle, "call_number": call, "media_type": "Unknown",
                     "note_list": [], "private": False}] if repo_handle else []
        objs.append({"_class": "Source", "handle": src_handle, "gramps_id": src_id, "title": src_title,
                     "author": _text(source.get("author")), "pubinfo": _text(source.get("pubinfo")),
                     "abbrev": _text(source.get("abbrev")), "change": now, "reporef_list": reporefs,
                     "media_list": [], "note_list": [], "attribute_list": [], "tag_list": [], "private": False})
        made.append({"kind": "source", "gramps_id": src_id, "title": src_title})

    note_handle, cit_handle = generate_handle(), generate_handle()
    tags = [await tag_for(gramps, _text(citation["tag"]), objs, now)] if _text(citation.get("tag")) else []
    objs.append({"_class": "Note", "handle": note_handle, "gramps_id": minted["N"],
                 "text": {"_class": "StyledText", "string": note_text(frn, srn), "tags": []},
                 "type": "Citation", "format": 0, "change": now, "tag_list": [], "private": False})
    objs.append({"_class": "Citation", "handle": cit_handle, "gramps_id": minted["C"],
                 "source_handle": src_handle, "page": page, "confidence": CONFIDENCE.index(confidence),
                 "change": now, "note_list": [note_handle], "media_list": [media_ref(media["handle"])],
                 "attribute_list": citation_attributes([], citation.get("attributes")), "tag_list": tags, "private": False})
    made += [{"kind": "citation", "gramps_id": minted["C"], "title": page},
             {"kind": "note", "gramps_id": minted["N"], "title": "Reference notes"}]
    records, done = list(await gramps.create_objects(objs)), []
    for kind, handle, gid in targets:
        try:
            obj = await gramps.get_object(KINDS[kind], handle)
            obj["citation_list"] = [*(obj.get("citation_list") or []), cit_handle]
            records += await gramps.update_object(KINDS[kind], handle, obj)
        except Exception as exc:  # noqa: BLE001
            await _take_back(gramps, records, [m["gramps_id"] for m in made], done, gid, exc)
        done.append(gid)

    result = {"created": made, "source": {"handle": src_handle, "gramps_id": src_id, "title": src_title},
              "citation": {"handle": cit_handle, "gramps_id": minted["C"]}, "media": media.get("gramps_id") or pid,
              "attached": [{"kind": k, "handle": h, "gramps_id": gid} for k, h, gid in targets],
              "scan": None, "scan_error": None}
    if scan is not None:
        try:
            await file_scan(paperless, cfg, doc, scan)
            result["scan"] = doc_id
        except Exception as exc:  # noqa: BLE001
            result["scan_error"] = str(exc)
    return result


async def _take_back(gramps: GrampsClient, records: list[dict], made: list[str], done: list[str], target: str,
                     exc: Exception):
    """Undo a create whose attach failed, in one Gramps transaction, and refuse the create"""
    reason = str(exc)[:300]
    try:
        await gramps.undo(records, f"Undo {', '.join(made)}")
    except Exception as undo_exc:  # noqa: BLE001
        on = f", attached to {', '.join(done)}," if done else ""
        raise CitationError(502, f"Couldn't attach the citation to {target}: {reason}. Undoing failed too, "
                                 f"so {', '.join(made)}{on} stay in Gramps: {str(undo_exc)[:300]}") from exc
    raise CitationError(502, f"Couldn't attach the citation to {target}, so nothing was made: {reason}") from exc


async def file_scan(paperless: PaperlessClient, cfg: SyncPaperlessConfig, doc: dict, scan: dict) -> None:
    """Set the scan's title, document type, correspondent, Source URL and date meaning"""
    patch = {"document_type": scan.get("document_type"), "correspondent": scan.get("correspondent")}
    if title := _text(scan.get("title")):
        patch["title"] = title
    values = {cf["field"]: cf.get("value") for cf in doc.get("custom_fields") or []}
    if cfg.source_url_field_id and (url := (scan.get("source_url") or "").strip()):
        values[cfg.source_url_field_id] = url
    if scan.get("date_meaning") and (meaning := date_meaning_field(await paperless.custom_fields())):
        values[meaning["id"]] = scan["date_meaning"]
    patch["custom_fields"] = [{"field": f, "value": v} for f, v in values.items()]
    await paperless.patch_document(doc["id"], patch)


def _rebuild_row(c: dict, kept: dict, notes: dict, sources: dict, tags: dict) -> dict:
    frn, srn, note = "", "", ""
    for h in c.get("note_list") or []:
        got = reference_notes(((notes.get(h) or {}).get("text") or {}).get("string") or "")
        if any(got):
            (frn, srn), note = got, h
            break
    src = sources.get(c.get("source_handle")) or {}
    return {"handle": c["handle"], "gramps_id": c.get("gramps_id") or "", "page": c.get("page") or "", "frn": frn, "srn": srn,
            "note": note, "attributes": [[a.get("type") or "", a.get("value") or ""] for a in c.get("attribute_list") or []],
            "tags": [tags.get(t, "") for t in c.get("tag_list") or []],
            "source": {"handle": src.get("handle") or "", "gramps_id": src.get("gramps_id") or "", "title": src.get("title") or ""},
            "draft": kept}


async def wizard_citations(gramps: GrampsClient, conn: sqlite3.Connection) -> list[dict]:
    """Every citation the wizard kept a draft for, as Gramps holds it now, newest first; deleted ones left out"""
    rows = conn.execute("SELECT citation_handle, record_type, draft FROM citation_drafts ORDER BY created_at DESC").fetchall()
    gate = asyncio.Semaphore(8)

    async def one(path: str, handle: str) -> dict | None:
        async with gate:
            try:
                return await gramps.get_object(path, handle)
            except Exception:  # noqa BLE001
                return None

    cits = await asyncio.gather(*(one("citations", r["citation_handle"]) for r in rows))
    found = [(c, {"type": r["record_type"], "draft": json.loads(r["draft"])}) for c, r in zip(cits, rows) if c]
    note_handles = sorted({h for c, _ in found for h in c.get("note_list") or []})
    src_handles = sorted({c.get("source_handle") for c, _ in found if c.get("source_handle")})
    notes = dict(zip(note_handles, await asyncio.gather(*(one("notes", h) for h in note_handles))))
    sources = dict(zip(src_handles, await asyncio.gather(*(one("sources", h) for h in src_handles))))
    tags = {t["handle"]: t.get("name") or "" for t in await gramps._paged("/tags/", keys="handle,name")}
    return [_rebuild_row(c, kept, notes, sources, tags) for c, kept in found]


async def rebuild(gramps: GrampsClient, conn: sqlite3.Connection, items: list[dict], tag: str) -> dict:
    """Write each rebuilt citation: page string, attributes and General form tag, then its reference notes"""
    now = int(datetime.now(timezone.utc).timestamp())
    done, failed = [], []
    for item in items:
        handle = item["handle"]
        try:
            cit = await gramps.get_object("citations", handle)
            if item.get("page") is not None:
                cit["page"] = item["page"].strip()
            if item.get("attributes") is not None:
                cit["attribute_list"] = citation_attributes(cit.get("attribute_list"), item["attributes"])
            if item.get("tagged") is not None:
                objs: list[dict] = []
                tag_handle = await tag_for(gramps, tag, objs, now)
                if objs:
                    await gramps.create_objects(objs)
                rest = [t for t in cit.get("tag_list") or [] if t != tag_handle]
                cit["tag_list"] = rest + ([tag_handle] if item["tagged"] else [])
            cit["change"] = now
            await gramps.update_object("citations", handle, cit)
            if item.get("frn") is not None and item.get("srn") is not None and item.get("note"):
                note = await gramps.get_object("notes", item["note"])
                note["text"] = {"_class": "StyledText", "string": note_text(item["frn"], item["srn"]), "tags": []}
                note["change"] = now
                await gramps.update_object("notes", item["note"], note)
            if item.get("draft"):
                keep_draft(conn, handle, item["draft"]["type"], item["draft"]["draft"])
            done.append(cit.get("gramps_id") or handle)
        except Exception as exc:  # noqa BLE001
            failed.append({"handle": handle, "error": str(exc)[:300]})
    return {"rebuilt": done, "failed": failed}
