"""Gramps Sources and Citations made in the citations wizard, and the Paperless scan filed with them"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone

from ..core.clients import GrampsClient, PaperlessClient
from ..core.config import SyncPaperlessConfig
from ..core.ids import generate_handle, next_sequential_id
from .ancestry_links import media_ref
from .codes import normalize

CONFIDENCE = ("Very Low", "Low", "Normal", "High", "Very High")
DATE_MEANING = "date meaning"


class CitationError(Exception):
    """A refused create, with the HTTP status that fits it"""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


def note_text(frn: str, srn: str) -> str:
    return f"FIRST REFERENCE NOTE:\n{frn.strip()}\n\nSHORT REFERENCE NOTE:\n{srn.strip()}"


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
                   doc_id: int) -> dict:
    """The Paperless document, its Gramps media, and the citations already on that media"""
    doc, fields = await asyncio.gather(paperless.get_document(doc_id), paperless.custom_fields())
    pid = gramps_id_of(cfg, doc)
    if not pid:
        raise CitationError(403, f"Paperless document #{doc_id} isn't synced to Gramps")
    media = await gramps.get_media_by_gramps_id(pid)
    cited = []
    if media:
        links = await gramps.get_media_backlinks(media["handle"])
        cits = await asyncio.gather(*(gramps.get_object("citations", h)
                                      for h in links.get("citation") or []))
        handles = sorted({c.get("source_handle") for c in cits if c.get("source_handle")})
        srcs = dict(zip(handles, await asyncio.gather(*(gramps.get_object("sources", h) for h in handles))))
        cited = sorted(({"gramps_id": c.get("gramps_id") or "", "page": c.get("page") or "",
                         "source": (srcs.get(c.get("source_handle")) or {}).get("title") or ""}
                        for c in cits), key=lambda c: c["gramps_id"])
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
    }


def _text(value) -> str:
    return " ".join(str(value or "").split())


async def _next_ids(gramps: GrampsClient, kinds: list[tuple[str, str]]) -> list[str]:
    taken = await asyncio.gather(*(gramps._paged(f"/{path}/", keys="gramps_id") for path, _ in kinds))
    return [next_sequential_id(prefix, {i["gramps_id"] for i in items if i.get("gramps_id")})
            for (_, prefix), items in zip(kinds, taken)]


async def create(gramps: GrampsClient, paperless: PaperlessClient, cfg: SyncPaperlessConfig,
                 doc_id: int, source: dict, citation: dict, scan: dict | None) -> dict:
    """Make the Source when new and the Citation with its note on the document's media, then file the scan"""
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
    objs.append({"_class": "Note", "handle": note_handle, "gramps_id": minted["N"],
                 "text": {"_class": "StyledText", "string": note_text(frn, srn), "tags": []},
                 "type": "Citation", "format": 0, "change": now, "tag_list": [], "private": False})
    objs.append({"_class": "Citation", "handle": cit_handle, "gramps_id": minted["C"],
                 "source_handle": src_handle, "page": page, "confidence": CONFIDENCE.index(confidence),
                 "change": now, "note_list": [note_handle], "media_list": [media_ref(media["handle"])],
                 "attribute_list": [], "tag_list": [], "private": False})
    made += [{"kind": "citation", "gramps_id": minted["C"], "title": page},
             {"kind": "note", "gramps_id": minted["N"], "title": "Reference notes"}]
    await gramps.create_objects(objs)

    result = {"created": made, "source": {"handle": src_handle, "gramps_id": src_id, "title": src_title},
              "citation": {"handle": cit_handle, "gramps_id": minted["C"]}, "media": media.get("gramps_id") or pid,
              "scan": None, "scan_error": None}
    if scan is not None:
        try:
            await file_scan(paperless, cfg, doc, scan)
            result["scan"] = doc_id
        except Exception as exc:  # noqa: BLE001
            result["scan_error"] = str(exc)
    return result


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
