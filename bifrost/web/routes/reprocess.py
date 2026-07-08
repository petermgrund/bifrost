"""Reprocess page + API. Preview and apply are the same generator (apply flag)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...modules import reprocess, sync_paperless
from ..runs import record_run

router = APIRouter(prefix="/reprocess", tags=["reprocess"])

# The library scan is restricted to this Paperless tag — the archive's
# documents tag (the first of the sync tags; 'img' docs are single images).
SCAN_TAG = "doc"


def _check_mode(mode: str) -> None:
    if mode not in (reprocess.MODE_WIDEST, reprocess.MODE_NARROWEST):
        raise HTTPException(400, f"mode must be '{reprocess.MODE_WIDEST}'"
                                 f" or '{reprocess.MODE_NARROWEST}'")


@router.get("")
async def reprocess_page(request: Request):
    return RedirectResponse(url="/#reprocess")


@router.get("/api/config")
async def reprocess_config(request: Request):
    """Read-only config for the section (Paperless doc links, scan tag)."""
    return {"public_url": request.app.state.cfg.sync_paperless.public_url,
            "scan_tag": SCAN_TAG}


class WidthsBody(BaseModel):
    doc_ref: str  # Paperless doc id (all digits) or a Gramps media id
    mode: str = reprocess.MODE_WIDEST
    apply: bool = False


@router.post("/api/widths")
async def normalize_widths(request: Request, body: WidthsBody):
    st = request.app.state
    ref = body.doc_ref.strip()
    if not ref:
        raise HTTPException(400, "Paperless document id or Gramps media id required")
    _check_mode(body.mode)
    if ref.isdigit():
        doc_id = int(ref)
    else:
        doc_id = await sync_paperless.paperless_id_for_media(st.gramps, ref.upper())
        if doc_id is None:
            raise HTTPException(
                404, f"no Gramps media '{ref.upper()}', or it has no Paperless ID attribute")

    gen = reprocess.run(st.paperless, doc_id, body.mode, apply=body.apply)
    job = "reprocess.widths" + ("" if body.apply else ".preview")
    run_id, events = await record_run(st.conn, job, gen)
    if body.apply:
        st.caches.clear()
    return {"run_id": run_id, "apply": body.apply, "doc_id": doc_id,
            "events": [e.__dict__ for e in events]}


@router.post("/api/scan")
async def scan_mixed(request: Request):
    """Measure every multi-page PDF tagged SCAN_TAG; list the mixed-width
    ones. Read-only, so no run is recorded."""
    st = request.app.state
    try:
        return await reprocess.scan_mixed_widths(st.paperless, SCAN_TAG)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


class BatchBody(BaseModel):
    doc_ids: list[int]
    mode: str = reprocess.MODE_WIDEST


@router.post("/api/batch")
async def batch_widths(request: Request, body: BatchBody):
    """Normalize the selected documents in one recorded run. The scan is the
    preview — this always applies."""
    st = request.app.state
    if not body.doc_ids:
        raise HTTPException(400, "no documents selected")
    _check_mode(body.mode)
    gen = reprocess.run_batch(st.paperless, body.doc_ids, body.mode)
    run_id, events = await record_run(st.conn, "reprocess.widths.batch", gen)
    st.caches.clear()
    return {"run_id": run_id, "apply": True,
            "events": [e.__dict__ for e in events]}
