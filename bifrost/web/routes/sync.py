"""Sync page + API. Preview and apply are the same generator (apply flag)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...modules import ocr, sync_paperless
from ...modules.sync_paperless import _doc_gramps_id
from ..runs import record_run

router = APIRouter(prefix="/sync", tags=["sync"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def sync_page(request: Request):
    # Bifrost is a single page now — deep-link to the section.
    return RedirectResponse(url="/#sync")


@router.get("/paperless")
async def paperless_page(request: Request):
    return RedirectResponse(url="/#sync")


@router.get("/api/paperless/config")
async def paperless_config(request: Request):
    """Read-only config for the Paperless Settings tab."""
    cfg = _state(request).cfg.sync_paperless
    return {
        "sync_tags": list(cfg.sync_tags),
        "public_url": cfg.public_url,
        "gramps_public_url": cfg.gramps_public_url,
        "transcription_tag_id": cfg.transcription_tag_id,
        "ocr_tag": cfg.ocr_tag,
    }


class PaperlessBody(BaseModel):
    force_transcriptions: bool = False
    transcriptions_only: bool = False
    versions_only: bool = False


def _paperless_job(body: PaperlessBody, preview: bool) -> str:
    if body.transcriptions_only:
        name = "sync.paperless.transcriptions"
    elif body.versions_only:
        name = "sync.paperless.versions"
    else:
        name = "sync.paperless"
    return f"{name}.preview" if preview else name


@router.post("/api/paperless/preview")
async def paperless_preview(request: Request, body: PaperlessBody):
    st = _state(request)
    gen = sync_paperless.sync(
        st.paperless, st.gramps, st.conn, st.cfg.sync_paperless,
        apply=False, force_transcriptions=body.force_transcriptions,
        transcriptions_only=body.transcriptions_only,
        versions_only=body.versions_only,
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
        versions_only=body.versions_only,
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


class OcrBody(BaseModel):
    force: bool = False
    single_doc_id: int | None = None


@router.post("/api/ocr/preview")
async def ocr_preview(request: Request, body: OcrBody = OcrBody()):
    st = _state(request)
    gen = ocr.run(st.paperless, st.gemini, st.conn, st.cfg.sync_paperless,
                  st.cfg.gemini, apply=False, force=body.force,
                  single_doc_id=body.single_doc_id)
    run_id, events = await record_run(st.conn, "ocr.gemini.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/ocr/apply")
async def ocr_apply(request: Request, body: OcrBody = OcrBody()):
    st = _state(request)
    gen = ocr.run(st.paperless, st.gemini, st.conn, st.cfg.sync_paperless,
                  st.cfg.gemini, apply=True, force=body.force,
                  single_doc_id=body.single_doc_id)
    run_id, events = await record_run(st.conn, "ocr.gemini", gen)
    st.caches.clear()  # content changed → downstream views/transcriptions stale
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}


@router.get("/api/ocr/pending")
async def ocr_pending(request: Request):
    st = _state(request)
    return {"count": await ocr.pending_count(st.paperless, st.conn, st.cfg.sync_paperless)}


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
