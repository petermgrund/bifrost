"""Sync page + API. Preview and apply are the same generator (apply flag)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...modules import sync_immich, sync_paperless
from ...modules.sync_paperless import _doc_gramps_id
from ..runs import record_run

router = APIRouter(prefix="/sync", tags=["sync"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def sync_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "sync.html", {})


@router.post("/api/immich/preview")
async def immich_preview(request: Request):
    st = _state(request)
    gen = sync_immich.sync(st.gramps, st.immich, st.conn, st.cfg.sync_immich, apply=False)
    run_id, events = await record_run(st.conn, "sync.immich.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/immich/apply")
async def immich_apply(request: Request):
    st = _state(request)
    gen = sync_immich.sync(st.gramps, st.immich, st.conn, st.cfg.sync_immich, apply=True)
    run_id, events = await record_run(st.conn, "sync.immich", gen)
    # Media and faces changed — every cached view is stale.
    st.caches.clear()
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}


class PaperlessBody(BaseModel):
    force_transcriptions: bool = False
    transcriptions_only: bool = False


def _paperless_job(body: PaperlessBody, preview: bool) -> str:
    name = "sync.paperless.transcriptions" if body.transcriptions_only else "sync.paperless"
    return f"{name}.preview" if preview else name


@router.post("/api/paperless/preview")
async def paperless_preview(request: Request, body: PaperlessBody):
    st = _state(request)
    gen = sync_paperless.sync(
        st.paperless, st.gramps, st.conn, st.cfg.sync_paperless,
        apply=False, force_transcriptions=body.force_transcriptions,
        transcriptions_only=body.transcriptions_only,
    )
    run_id, events = await record_run(st.conn, _paperless_job(body, True), gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/paperless/apply")
async def paperless_apply(request: Request, body: PaperlessBody):
    st = _state(request)
    gen = sync_paperless.sync(
        st.paperless, st.gramps, st.conn, st.cfg.sync_paperless,
        apply=True, force_transcriptions=body.force_transcriptions,
        transcriptions_only=body.transcriptions_only,
    )
    run_id, events = await record_run(st.conn, _paperless_job(body, False), gen)
    st.caches.clear()
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}


class ResyncMediaBody(BaseModel):
    media_id: str
    apply: bool = False


@router.post("/api/paperless/resync-media")
async def paperless_resync_media(request: Request, body: ResyncMediaBody):
    """Resync just one media object's transcription notes, by Gramps media id."""
    st = _state(request)
    media_id = body.media_id.strip()
    if not media_id:
        raise HTTPException(400, "media id required")
    doc_id = await sync_paperless.paperless_id_for_media(st.gramps, media_id)
    if doc_id is None:
        raise HTTPException(
            404, f"no Gramps media '{media_id}', or it has no Paperless ID attribute")
    gen = sync_paperless.sync(
        st.paperless, st.gramps, st.conn, st.cfg.sync_paperless,
        apply=body.apply, force_transcriptions=True,
        transcriptions_only=True, single_doc_id=doc_id,
    )
    job = "sync.paperless.resync-media" + ("" if body.apply else ".preview")
    run_id, events = await record_run(st.conn, job, gen)
    if body.apply:
        st.caches.clear()
    return {"run_id": run_id, "apply": body.apply, "media_id": media_id,
            "doc_id": doc_id, "events": [e.__dict__ for e in events]}


@router.get("/api/paperless/pending")
async def paperless_pending(request: Request):
    """Tagged documents with no gramps_id yet — the inbox count."""
    st = _state(request)
    cfg = st.cfg.sync_paperless
    tag_ids = []
    for name in cfg.sync_tags:
        tid = await st.paperless.resolve_tag_id(name)
        if tid is not None:
            tag_ids.append(tid)
    docs = await st.paperless.list_documents_by_tags(tag_ids)
    pending = [d for d in docs if not _doc_gramps_id(d, cfg.gramps_id_field_id)]
    return {"count": len(pending), "total_tagged": len(docs)}
