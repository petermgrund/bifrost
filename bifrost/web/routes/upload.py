"""Upload wizard: ingest a Paperless doc, edit metadata, OCR + house-style
autofill, mint a Gramps media object. The citation stage reuses the existing
/citations/api/compose-dump and /citations/api/save endpoints unchanged."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import Response

from ...core.clients.anthropic import AnthropicError
from ...modules import citations
from ...modules import ocr as ocr_mod
from ...modules import sync_paperless as sp_mod
from ...modules import upload as upload_mod
from ..runs import record_run

router = APIRouter(prefix="/upload", tags=["upload"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def upload_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "upload.html", {})


# --- ingest ---

@router.post("/api/ingest")
async def ingest(request: Request, filename: str, ocr: bool = False):
    st = _state(request)
    data = await request.body()
    if not data:
        raise HTTPException(400, "empty upload")
    mime = request.headers.get("content-type") or "application/octet-stream"
    try:
        task = await upload_mod.ingest(
            st.paperless, st.cfg.sync_paperless, filename, data, mime, ocr)
    except Exception as exc:  # noqa: BLE001 — surface the Paperless error verbatim
        raise HTTPException(502, f"upload failed: {exc}") from exc
    st.caches.pop("upload_candidates", None)
    return {"task": task}


@router.get("/api/ingest-status")
async def ingest_status(request: Request, task: str):
    return await upload_mod.ingest_status(_state(request).paperless, task)


# --- preview (proxied so the browser never needs the Paperless token) ---

@router.get("/api/preview/{doc_id}")
async def preview(request: Request, doc_id: int):
    content, mime = await _state(request).paperless.download_original(doc_id)
    return Response(content, media_type=mime,
                    headers={"Cache-Control": "private, max-age=300"})


# --- OCR one doc (immediately, in place) ---

@router.post("/api/ocr/{doc_id}")
async def ocr_doc(request: Request, doc_id: int):
    st = _state(request)
    if not st.gemini.configured:
        raise HTTPException(400, "no Gemini API key configured")
    if not await upload_mod.ensure_ocr_tag(st.paperless, st.cfg.sync_paperless, doc_id):
        raise HTTPException(400, "no OCR tag configured (sync.paperless.ocr_tag)")
    gen = ocr_mod.run(st.paperless, st.gemini, st.conn, st.cfg.sync_paperless,
                      st.cfg.gemini, apply=True, force=True, single_doc_id=doc_id)
    _run_id, events = await record_run(st.conn, "upload.ocr", gen)
    errs = upload_mod.ocr_errors(events)
    result = await upload_mod.read_transcript(st.paperless, doc_id)
    if errs and result["chars"] == 0:
        raise HTTPException(502, "; ".join(errs))
    return {**result, "errors": errs}


# --- form options / load / save ---

@router.get("/api/options")
async def get_options(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("upload_options") is None or refresh:
        st.caches["upload_options"] = await upload_mod.options(
            st.paperless, st.cfg.sync_paperless)
    return st.caches["upload_options"]


@router.get("/api/documents")
async def get_documents(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("upload_candidates") is None or refresh:
        st.caches["upload_candidates"] = await upload_mod.list_candidates(
            st.paperless, st.cfg.sync_paperless)
    return st.caches["upload_candidates"]


@router.get("/api/doc/{doc_id}")
async def get_doc(request: Request, doc_id: int):
    st = _state(request)
    try:
        return await upload_mod.load_doc(st.paperless, st.cfg.sync_paperless, doc_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/api/fields/{doc_id}")
async def save_fields(request: Request, doc_id: int, form: dict = Body(...)):
    st = _state(request)
    try:
        await upload_mod.save_fields(st.paperless, st.cfg.sync_paperless, doc_id, form)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"save failed: {exc}") from exc
    return {"saved": True}


@router.post("/api/autofill/{doc_id}")
async def autofill(request: Request, doc_id: int):
    st = _state(request)
    if not st.anthropic.configured:
        raise HTTPException(400, "no Anthropic API key configured")
    house = upload_mod.paperless_house_style(st.cfg.sync_paperless.house_style_path)
    if not house:
        raise HTTPException(400, "house-style file not found on the server")
    tr = await upload_mod.read_transcript(st.paperless, doc_id)
    if not tr["transcript"]:
        raise HTTPException(400, "no transcript yet — run OCR first")
    if st.caches.get("upload_options") is None:
        st.caches["upload_options"] = await upload_mod.options(
            st.paperless, st.cfg.sync_paperless)
    try:
        guesses = await upload_mod.autofill(
            st.anthropic, tr["transcript"], house, st.caches["upload_options"])
    except (AnthropicError, ValueError) as exc:
        raise HTTPException(502, f"autofill failed: {exc}") from exc
    return {"guesses": guesses}


# --- mint the Gramps media object ---

@router.post("/api/to-gramps/{doc_id}")
async def to_gramps(request: Request, doc_id: int):
    st = _state(request)
    gen = sp_mod.sync(st.paperless, st.gramps, st.conn, st.cfg.sync_paperless,
                      apply=True, single_doc_id=doc_id)
    _run_id, events = await record_run(st.conn, "upload.to-gramps", gen)
    try:
        result = await upload_mod.resolve_minted(
            st.paperless, st.gramps, st.cfg.sync_paperless, doc_id, events)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    st.caches.pop("upload_candidates", None)
    for key in list(st.caches):
        if key.startswith("citations_"):
            st.caches.pop(key, None)  # new media changes the citation pickers
    return result


# --- event picker (all events, searchable) ---

@router.get("/api/events")
async def get_events(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("upload_events") is None or refresh:
        st.caches["upload_events"] = await citations.all_events(st.gramps)
    return st.caches["upload_events"]
