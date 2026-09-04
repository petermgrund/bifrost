"""Attach Paperless documents downloaded from Ancestry to the Gramps citations Ancestry created"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import AsyncIterator

from ..core.clients import GrampsClient
from ..core.clients.paperless import PaperlessClient
from ..core.config import SyncPaperlessConfig
from ..core.events import SyncEvent

APID_RE = re.compile(r"1,(\d+)::(\d+)")
DBID_RE = re.compile(r"[?&]dbid=(\d+)")
H_RE = re.compile(r"[?&]h=(\d+)")


def record_key(url: str | None) -> tuple[str, str] | None:
    """(dbid, h) of an Ancestry record URL"""
    if not url or "ancestry" not in url.lower():
        return None
    dbid, h = DBID_RE.search(url), H_RE.search(url)
    return (dbid.group(1), h.group(1)) if dbid and h else None


def apid_key(value: str | None) -> tuple[str, str] | None:
    """(dbid, h) of a citation's _APID attribute"""
    m = APID_RE.search(value or "")
    return (m.group(1), m.group(2)) if m else None


def media_ref(handle: str) -> dict:
    return {"_class": "MediaRef", "ref": handle, "rect": None, "private": False,
            "attribute_list": [], "citation_list": [], "note_list": []}


def configured(cfg: SyncPaperlessConfig) -> bool:
    return bool(cfg.source_url_field_id and cfg.gramps_id_field_id)


async def apid_index(gramps: GrampsClient) -> dict[tuple[str, str], list[dict]]:
    """Citations by Ancestry record key, from their _APID attributes"""
    index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in await gramps._paged("/citations/", page_size=1000,
                                 keys="handle,gramps_id,media_list,attribute_list"):
        for a in c.get("attribute_list") or []:
            if a.get("type") == "_APID" and (key := apid_key(a.get("value"))):
                index[key].append(c)
    return index


async def candidates(paperless: PaperlessClient, cfg: SyncPaperlessConfig,
                     doc_ids: list[int] | None = None) -> tuple[list[dict], list[dict]]:
    """(linkable docs, docs with an Ancestry URL but no Gramps media yet)"""
    docs = await paperless.list_documents()
    if doc_ids is not None:
        wanted = set(doc_ids)
        docs = [d for d in docs if d["id"] in wanted]
    rows, unsynced = [], []
    for d in docs:
        key = record_key(paperless.custom_field_value(d, cfg.source_url_field_id))
        if key is None:
            continue
        gid = paperless.custom_field_value(d, cfg.gramps_id_field_id)
        if not gid:
            unsynced.append(d)
            continue
        rows.append({"doc": d, "key": key, "gramps_id": str(gid).strip().upper()})
    return rows, unsynced


def _progress(label: str, done: int, total: int) -> SyncEvent:
    return SyncEvent(kind="progress", detail=label,
                     data={"done": done, "total": total,
                           "percent": round(100 * done / total) if total else 100})


def _doc_row(doc: dict, **kw) -> dict:
    return dict(kind="item", entity="doc", source_id=str(doc["id"]),
                title=doc.get("title") or f"#{doc['id']}", **kw)


async def link(
    gramps: GrampsClient,
    paperless: PaperlessClient,
    cfg: SyncPaperlessConfig,
    apply: bool,
    selected: set[str] | None = None,
    doc_ids: list[int] | None = None,
    index: dict | None = None,
) -> AsyncIterator[SyncEvent]:
    """Attach each Ancestry document's media object to the citations carrying its _APID"""
    rows, unsynced = await candidates(paperless, cfg, doc_ids)
    yield SyncEvent(kind="started",
                    detail=f"{len(rows)} Ancestry document(s) with a Gramps media object")
    counts = {"citations_linked": 0, "in_place": 0, "unmatched": 0, "unsynced": len(unsynced),
              "errors": 0}
    for d in unsynced:
        yield SyncEvent(**_doc_row(d), action="failed",
                        detail="not synced to Gramps yet, run the Paperless sync first")
    if rows:
        yield _progress("Indexing citations", 0, len(rows) + 1)
        if index is None:
            index = await apid_index(gramps)
    for i, row in enumerate(sorted(rows, key=lambda r: r["doc"]["id"])):
        yield _progress("Matching records", i + 1, len(rows) + 1)
        doc, key, gid = row["doc"], row["key"], row["gramps_id"]
        media = await gramps.get_media_by_gramps_id(gid)
        if not media:
            counts["errors"] += 1
            yield SyncEvent(**_doc_row(doc), action="failed", gramps_id=gid,
                            detail=f"media {gid} no longer exists in Gramps")
            continue
        handle = media["handle"]
        matches = index.get(key, []) if index else []
        if not matches:
            counts["unmatched"] += 1
            yield SyncEvent(**_doc_row(doc), action="failed", gramps_id=gid,
                            detail=f"no citation carries _APID 1,{key[0]}::{key[1]} "
                                   "(Ancestry re-issued the record id), attach it by hand")
            continue
        for c in matches:
            if any(r.get("ref") == handle for r in c.get("media_list") or []):
                counts["in_place"] += 1
                continue
            source_id = f"{doc['id']}/{c['handle']}"
            cols = {"media": gid, "record": f"dbid {key[0]}, h {key[1]}"}
            if not apply:
                yield SyncEvent(kind="item", entity="citation", action="would_update",
                                source_id=source_id, gramps_id=c["gramps_id"],
                                title=doc.get("title") or f"#{doc['id']}", data={"cols": cols})
                continue
            if selected is not None and f"citation:{source_id}" not in selected:
                continue
            try:
                full = await gramps.get_object("citations", c["handle"])
                if not any(r.get("ref") == handle for r in full.get("media_list") or []):
                    full.setdefault("media_list", []).append(media_ref(handle))
                    await gramps.update_object("citations", c["handle"], full)
                    c["media_list"] = full["media_list"]
            except Exception as exc:  # noqa: BLE001
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="citation", action="failed",
                                source_id=source_id, gramps_id=c["gramps_id"],
                                title=doc.get("title") or f"#{doc['id']}", detail=str(exc)[:200])
                continue
            counts["citations_linked"] += 1
            yield SyncEvent(kind="item", entity="citation", action="updated",
                            source_id=source_id, gramps_id=c["gramps_id"],
                            title=doc.get("title") or f"#{doc['id']}", data={"cols": cols})
    if rows:
        yield _progress("Matching records", len(rows) + 1, len(rows) + 1)
    yield SyncEvent(kind="summary", data=counts)
