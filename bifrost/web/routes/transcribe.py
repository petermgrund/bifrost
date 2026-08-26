"""Transcribe"""

from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...modules import ocr, sync_paperless
from ..runs import record_run

router = APIRouter(prefix="/transcribe", tags=["transcribe"])


@router.get("")
async def transcribe_page(request: Request):
    return RedirectResponse(url="/#transcribe")


class RunBody(BaseModel):
    media_id: str


@router.post("/api/run")
async def run_for_media(request: Request, body: RunBody):
    st = request.app.state
    media_id = body.media_id.strip().upper()
    if not media_id:
        raise HTTPException(400, "media id required")
    doc_id = await sync_paperless.paperless_id_for_media(st.gramps, media_id)
    if doc_id is None:
        raise HTTPException(
            404, f"no Gramps media '{media_id}', or it has no Paperless ID attribute")

    gen = ocr.run(st.paperless, st.gemini, st.conn, st.cfg.sync_paperless,
                  st.cfg.gemini, apply=True, force=True, single_doc_id=doc_id)
    _, ocr_events = await record_run(st.conn, "ocr.gemini", gen)

    summary = next((e.data for e in ocr_events if e.kind == "summary"), None) or {}
    if not summary.get("transcribed"):
        err = next((e for e in ocr_events if e.kind == "error"), None)
        if err is not None:
            raise HTTPException(409, err.detail)
        failed = next(
            (e for e in ocr_events if e.kind == "item" and e.action == "failed"), None)
        if failed is not None:
            raise HTTPException(502, f"OCR failed: {failed.detail}")
        raise HTTPException(
            409, f"doc #{doc_id} is not tagged '{st.cfg.sync_paperless.ocr_tag}' "
                 f"in Paperless")

    gen = sync_paperless.sync(
        st.paperless, st.gramps, st.conn, st.cfg.sync_paperless,
        apply=True, force_transcriptions=True, transcriptions_only=True,
        single_doc_id=doc_id)
    _, tx_events = await record_run(st.conn, "sync.paperless.transcriptions", gen)

    st.caches.clear()
    return {"media_id": media_id, "doc_id": doc_id,
            "ocr_events": [e.__dict__ for e in ocr_events],
            "tx_events": [e.__dict__ for e in tx_events]}


@router.get("/api/lookup/{media_id}")
async def lookup(request: Request, media_id: str):
    """What a Run would transcribe, for the confirmation modal"""
    st = request.app.state
    mid = media_id.strip().upper()
    doc_id = await sync_paperless.paperless_id_for_media(st.gramps, mid)
    if doc_id is None:
        raise HTTPException(
            404, f"no Gramps media '{mid}', or it has no Paperless ID attribute")
    media = await st.gramps.get_media_by_gramps_id(mid)
    try:
        doc = await st.paperless.get_document(doc_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Paperless document #{doc_id} unavailable: {exc}")
    ocr_tag = st.cfg.sync_paperless.ocr_tag
    tagged = False
    if ocr_tag:
        tag_id = await st.paperless.resolve_tag_id(ocr_tag)
        tagged = bool(tag_id and tag_id in (doc.get("tags") or []))
    return {
        "media_id": mid,
        "media_title": (media or {}).get("desc") or "",
        "doc_id": doc_id,
        "doc_title": doc.get("title") or "",
        "chars": len((doc.get("content") or "").strip()),
        "ocr_tag": ocr_tag,
        "ocr_tagged": tagged,
    }


@router.get("/api/config")
async def transcribe_config(request: Request):
    cfg = request.app.state.cfg
    # house_style_path isn't on the config dataclass
    house_style = ""
    try:
        raw = yaml.safe_load(cfg.config_path.read_text()) or {}
        house_style = ((raw.get("sync") or {}).get("paperless") or {}).get("house_style_path") or ""
    except Exception:
        pass
    return {
        "model": cfg.gemini.model,
        "house_style_path": house_style,
        "gramps_public_url": cfg.sync_paperless.gramps_public_url,
    }
