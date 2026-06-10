"""Sync page + API. Preview and apply are the same generator (apply flag)."""

from __future__ import annotations

from fastapi import APIRouter, Request
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
