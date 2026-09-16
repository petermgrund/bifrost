"""Ancestry record links"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...core.clients.paperless import PaperlessError
from ...modules import ancestry_links, sync_paperless
from ..runs import record_run

router = APIRouter(prefix="/ancestry", tags=["ancestry"])


def _state(request: Request):
    return request.app.state


class LinksBody(BaseModel):
    selected: list[str] | None = None
    doc_ids: list[int] | None = None


def _require(request: Request):
    st = _state(request)
    if not ancestry_links.configured(st.cfg.sync_paperless):
        raise HTTPException(
            400, "sync.paperless.source_url_field_id and gramps_id_field_id are both required")
    return st


@router.get("/api/links/config")
async def links_config(request: Request) -> dict:
    return {"enabled": ancestry_links.configured(_state(request).cfg.sync_paperless)}


@router.post("/api/links/preview")
async def links_preview(request: Request, body: LinksBody = LinksBody()):
    st = _require(request)
    gen = ancestry_links.link(st.gramps, st.paperless, st.cfg.sync_paperless,
                              apply=False, doc_ids=body.doc_ids, cache=st.caches)
    run_id, events = await record_run(st.conn, "ancestry.links.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/links/apply")
async def links_apply(request: Request, body: LinksBody = LinksBody()):
    st = _require(request)
    gen = ancestry_links.link(
        st.gramps, st.paperless, st.cfg.sync_paperless, apply=True,
        selected=set(body.selected) if body.selected is not None else None,
        doc_ids=body.doc_ids, cache=st.caches)
    run_id, events = await record_run(st.conn, "ancestry.links", gen)
    index = st.caches.get(ancestry_links.INDEX_CACHE_KEY)
    st.caches.clear()
    if index:
        st.caches[ancestry_links.INDEX_CACHE_KEY] = index
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}


class IngestBody(BaseModel):
    doc_ids: list[int]


@router.post("/api/ingest")
async def ingest(request: Request, body: IngestBody):
    """Tag, sync and link freshly uploaded Ancestry documents in one call"""
    st = _require(request)
    cfg = st.cfg.sync_paperless
    if not body.doc_ids:
        raise HTTPException(400, "doc_ids is empty")
    tag_name = cfg.sync_tags[0] if cfg.sync_tags else ""
    tag_id = await st.paperless.resolve_tag_id(tag_name) if tag_name else None
    if tag_id is None:
        raise HTTPException(400, f"Paperless has no tag named {tag_name!r} (sync.paperless.sync_tags)")
    lines: list[str] = []
    tagged = 0
    for doc_id in body.doc_ids:
        try:
            doc = await st.paperless.get_document(doc_id)
        except PaperlessError as exc:
            lines.append(f"#{doc_id}: not in Paperless ({exc})")
            continue
        tags = list(doc.get("tags") or [])
        if tag_id not in tags:
            await st.paperless.patch_tags(doc_id, tags + [tag_id])
            tagged += 1
    lines.append(f"tagged {tagged} document(s) with {tag_name}")

    synced = {"created": 0, "errors": 0}
    for doc_id in body.doc_ids:
        gen = sync_paperless.sync(st.paperless, st.gramps, st.conn, cfg, apply=True,
                                  single_doc_id=doc_id)
        _run_id, events = await record_run(st.conn, "sync.paperless", gen)
        for e in events:
            if e.kind == "item" and e.action == "created":
                synced["created"] += 1
                lines.append(f"#{doc_id}: media {e.gramps_id} created")
            elif e.kind == "item" and e.action == "failed":
                synced["errors"] += 1
                lines.append(f"#{doc_id}: sync failed: {e.detail}")
    st.caches.clear()

    gen = ancestry_links.link(st.gramps, st.paperless, cfg, apply=True, doc_ids=body.doc_ids,
                              cache=st.caches)
    _run_id, events = await record_run(st.conn, "ancestry.links", gen)
    index = st.caches.get(ancestry_links.INDEX_CACHE_KEY)
    st.caches.clear()
    if index:
        st.caches[ancestry_links.INDEX_CACHE_KEY] = index
    summary = next((e.data for e in events if e.kind == "summary"), {})
    for e in events:
        if e.kind != "item":
            continue
        doc = e.source_id.split("/")[0]
        if e.action == "updated":
            lines.append(f"#{doc}: attached to citation {e.gramps_id}")
        elif e.action == "failed":
            lines.append(f"#{doc}: {e.detail}")
    return {"tagged": tagged, "synced": synced, "linked": summary, "lines": lines}
