"""Citations page + API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...core.clients.anthropic import AnthropicError
from ...modules import citations

router = APIRouter(prefix="/citations", tags=["citations"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def citations_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "citations.html", {})


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
    dump: str
    media_handle: str | None = None
    event_context: str | None = None


@router.post("/api/compose-dump")
async def compose_dump(request: Request, body: DumpBody):
    st = _state(request)
    if not st.anthropic.configured:
        raise HTTPException(400, "no Anthropic API key configured")
    if not body.dump.strip() and not (body.event_context or "").strip():
        raise HTTPException(400, "nothing to compose from")
    if st.caches.get("citations_context") is None:
        st.caches["citations_context"] = await citations.context(st.gramps)
    ctx = st.caches["citations_context"]
    media = None
    if body.media_handle:
        media = await st.gramps.get_object("media", body.media_handle)
    try:
        result = await citations.compose_from_dump(
            st.anthropic, body.dump, media, ctx["sources"], ctx["repositories"],
            body.event_context)
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
    # the upload wizard caches all events with a cited flag — a save that
    # attaches a citation to an event makes that flag stale.
    st.caches.pop("upload_events", None)
    return created
