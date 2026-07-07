"""Transcribe — Gemini OCR for one media object's document, end to end.

POST /transcribe/api/run takes a Gramps media id, resolves it to the Paperless
doc via the 'Paperless ID' attribute, OCRs it in place (force), then rewrites
the Transcription note back onto the Gramps media. One field, one button."""

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
    # Bifrost is a single page now — deep-link to the section.
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

    # Unless the doc was really transcribed, stop here and say why — falling
    # through would rewrite the note from the OLD text and report success.
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
                 f"in Paperless — tag it there first")

    gen = sync_paperless.sync(
        st.paperless, st.gramps, st.conn, st.cfg.sync_paperless,
        apply=True, force_transcriptions=True, transcriptions_only=True,
        single_doc_id=doc_id)
    _, tx_events = await record_run(st.conn, "sync.paperless.transcriptions", gen)

    st.caches.clear()
    return {"media_id": media_id, "doc_id": doc_id,
            "ocr_events": [e.__dict__ for e in ocr_events],
            "tx_events": [e.__dict__ for e in tx_events]}


@router.get("/api/config")
async def transcribe_config(request: Request):
    """Read-only config for the Configuration expander."""
    cfg = request.app.state.cfg
    # house_style_path isn't on the dataclass — read it from the raw YAML.
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
