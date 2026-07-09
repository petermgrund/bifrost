"""Citations page + API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...core.clients.anthropic import AnthropicError
from ...core.clients.paperless import PaperlessError
from ...modules import citations, sync_paperless

router = APIRouter(prefix="/citations", tags=["citations"])


def _state(request: Request):
    return request.app.state


async def _media_citations_cached(st, media_handle: str) -> list[dict]:
    """media_citations scans every citation in the tree — cache per handle so
    the lookup and the compose that follows don't each pay for a full scan.
    The citations_ prefix ties invalidation to the save route's cache clear."""
    key = f"citations_mediacits_{media_handle}"
    if st.caches.get(key) is None:
        st.caches[key] = await citations.media_citations(st.gramps, media_handle)
    return st.caches[key]


@router.get("")
async def citations_page(request: Request):
    # Bifrost is a single page now — deep-link to the section.
    return RedirectResponse(url="/#citations")


@router.get("/api/context")
async def get_context(request: Request):
    st = _state(request)
    if st.caches.get("citations_context") is None:
        st.caches["citations_context"] = await citations.context(st.gramps)
    ctx = st.caches["citations_context"]
    return {**ctx, "llm": st.anthropic.configured,
            "gramps_url": st.cfg.sync_paperless.gramps_public_url}


@router.get("/api/media")
async def get_media(request: Request, uncited: bool = False, refresh: bool = False):
    st = _state(request)
    key = f"citations_media_{uncited}"
    if st.caches.get(key) is None or refresh:
        st.caches[key] = await citations.media_listing(st.gramps, uncited_only=uncited)
    return st.caches[key]


@router.get("/api/media/{gramps_id}")
async def get_media_by_id(request: Request, gramps_id: str):
    st = _state(request)
    media = await st.gramps.get_media_by_gramps_id(gramps_id.strip().upper())
    if not media:
        raise HTTPException(404, f"no Gramps media '{gramps_id}'")
    paperless_id = next((a.get("value") for a in media.get("attribute_list", [])
                         if a.get("type") == "Paperless ID"), None)
    cits = await _media_citations_cached(st, media["handle"])
    return {"handle": media["handle"], "gramps_id": media["gramps_id"],
            "title": media.get("desc") or media["gramps_id"],
            "paperless_id": paperless_id,
            "citations": [{"gramps_id": c["gramps_id"], "page": c["page"],
                           "source_title": c["source_title"]} for c in cits]}


@router.get("/api/paperless/{media_gramps_id}")
async def get_paperless_details(request: Request, media_gramps_id: str):
    """Pullable bits of the media's Paperless doc: transcript, source URL, notes."""
    st = _state(request)
    doc_id = await sync_paperless.paperless_id_for_media(
        st.gramps, media_gramps_id.strip().upper())
    if doc_id is None:
        raise HTTPException(
            404, f"no Gramps media '{media_gramps_id}', or it has no Paperless ID attribute")
    try:
        doc = await st.paperless.get_document(doc_id)
    except PaperlessError as exc:
        raise HTTPException(502, f"Paperless document #{doc_id} unavailable: {exc}") from exc
    fid = st.cfg.sync_paperless.source_url_field_id
    return {
        "doc_id": doc_id,
        "transcript": (doc.get("content") or "").strip(),
        "source_url": (st.paperless.get_custom_field_value(doc, fid) or "") if fid else "",
        "notes": "\n\n".join(t for n in doc.get("notes") or []
                             if (t := (n.get("note") or "").strip())),
    }


@router.get("/api/uncited-events")
async def get_uncited_events(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("citations_uncited_events") is None or refresh:
        st.caches["citations_uncited_events"] = await citations.uncited_events(st.gramps)
    return st.caches["citations_uncited_events"]


@router.get("/api/event/{handle}")
async def get_event(request: Request, handle: str):
    st = _state(request)
    if st.caches.get("citations_cited_set") is None:
        st.caches["citations_cited_set"] = await citations.cited_media_set(st.gramps)
    return await citations.event_detail(
        st.gramps, handle, st.caches["citations_cited_set"])


class ComposeBody(BaseModel):
    record_type: str | None = None
    fields: dict = {}
    media_handle: str | None = None
    source_handle: str | None = None
    event_context: str | None = None


@router.post("/api/compose")
async def compose(request: Request, body: ComposeBody):
    st = _state(request)
    if not st.anthropic.configured:
        raise HTTPException(400, "no Anthropic API key configured — fill the draft manually")
    media = None
    if body.media_handle:
        media = await st.gramps.get_object("media", body.media_handle)
    existing_source = None
    if body.source_handle:
        existing_source = await st.gramps.get_object("sources", body.source_handle)
    try:
        draft = await citations.compose(
            st.anthropic, body.record_type, body.fields, media, existing_source,
            body.event_context)
    except AnthropicError as exc:
        raise HTTPException(502, f"composition failed: {exc}") from exc
    return draft


class DumpBody(BaseModel):
    subject: str = ""     # what the citation represents — required unless event-driven
    transcript: str = ""  # record transcript (pulled from Paperless or pasted)
    urls: str = ""        # one per line, optional role after each
    dump: str = ""        # catch-all for anything else
    media_handle: str | None = None
    event_context: str | None = None


@router.post("/api/compose-dump")
async def compose_dump(request: Request, body: DumpBody):
    st = _state(request)
    if not st.anthropic.configured:
        raise HTTPException(400, "no Anthropic API key configured")
    if not body.subject.strip() and not (body.event_context or "").strip():
        raise HTTPException(400, "describe what this citation represents")
    if st.caches.get("citations_context") is None:
        st.caches["citations_context"] = await citations.context(st.gramps)
    ctx = st.caches["citations_context"]
    media = None
    existing = None
    if body.media_handle:
        media = await st.gramps.get_object("media", body.media_handle)
        existing = await _media_citations_cached(st, body.media_handle)
    try:
        result = await citations.compose_from_dump(
            st.anthropic, body.dump, media, ctx["sources"], ctx["repositories"],
            body.event_context, subject=body.subject,
            transcript=body.transcript, urls=body.urls,
            existing_citations=existing)
    except AnthropicError as exc:
        raise HTTPException(502, f"composition failed: {exc}") from exc
    return result


class SaveBody(BaseModel):
    draft: dict
    media_handle: str | None = None
    repository_handle: str | None = None
    source_handle: str | None = None
    event_handle: str | None = None


@router.post("/api/save")
async def save(request: Request, body: SaveBody):
    st = _state(request)
    try:
        created = await citations.save(
            st.gramps, st.conn, body.draft,
            body.media_handle, body.repository_handle, body.source_handle,
            body.event_handle)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    for key in list(st.caches):
        if key.startswith("citations_"):
            st.caches.pop(key, None)
    return created
