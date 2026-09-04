"""Citations page + API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from ...core.clients.anthropic import AnthropicError
from ...core.clients.gramps import GrampsError
from ...core.clients.paperless import PaperlessError
from ...modules import citations, sync_paperless

router = APIRouter(prefix="/citations", tags=["citations"])


def _state(request: Request):
    return request.app.state


async def _media_citations_cached(st, media_handle: str) -> list[dict]:
    key = f"citations_mediacits_{media_handle}"
    if st.caches.get(key) is None:
        st.caches[key] = await citations.media_citations(st.gramps, media_handle)
    return st.caches[key]


@router.get("")
async def citations_page(request: Request):
    return RedirectResponse(url="/#citations")


@router.get("/api/context")
async def get_context(request: Request):
    st = _state(request)
    if st.caches.get("citations_context") is None:
        st.caches["citations_context"] = await citations.context(st.gramps)
    ctx = st.caches["citations_context"]
    return {**ctx, "llm": st.anthropic.configured,
            "house_style": citations.has_house_style(),
            "gramps_url": st.cfg.sync_paperless.gramps_public_url}


@router.get("/api/media")
async def get_media(request: Request, q: str = "", mode: str = "", limit: int = 10):
    gramps = _state(request).gramps
    limit = max(1, min(limit, 50))
    if mode == "changed":
        return await citations.recently_changed_media(gramps, limit)
    return await citations.search_media(gramps, q, limit)


@router.get("/api/bookmarks")
async def get_bookmarks(request: Request):
    st = _state(request)
    if st.caches.get("citations_bookmarks") is None:
        st.caches["citations_bookmarks"] = await citations.bookmarks(st.gramps)
    return st.caches["citations_bookmarks"]


@router.get("/api/recent")
async def get_recent(request: Request, limit: int = 10):
    st = _state(request)
    return await citations.recent_details(st.gramps, citations.recent_minted(st.conn, limit))


@router.get("/api/thumbnail/{handle}")
async def media_thumbnail(request: Request, handle: str, size: int = 64):
    try:
        content, mime = await _state(request).gramps.media_thumbnail(handle, size)
    except GrampsError as exc:
        raise HTTPException(404, str(exc)[:200]) from exc
    return Response(content, media_type=mime, headers={"Cache-Control": "public, max-age=3600"})


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


async def _paperless_details(st, doc_id: int) -> dict:
    doc = await st.paperless.get_document(doc_id)
    fid = st.cfg.sync_paperless.source_url_field_id
    return {
        "doc_id": doc_id,
        "transcript": (doc.get("content") or "").strip(),
        "source_url": (st.paperless.custom_field_value(doc, fid) or "") if fid else "",
        "notes": "\n\n".join(t for n in doc.get("notes") or []
                             if (t := (n.get("note") or "").strip())),
    }


def _paperless_id(media: dict) -> int | None:
    for attr in media.get("attribute_list", []):
        if attr.get("type") == "Paperless ID":
            try:
                return int(attr["value"])
            except (ValueError, TypeError, KeyError):
                return None
    return None


@router.get("/api/paperless/{media_gramps_id}")
async def get_paperless_details(request: Request, media_gramps_id: str):
    st = _state(request)
    doc_id = await sync_paperless.paperless_id_for_media(
        st.gramps, media_gramps_id.strip().upper())
    if doc_id is None:
        raise HTTPException(
            404, f"no Gramps media '{media_gramps_id}', or it has no Paperless ID attribute")
    try:
        return await _paperless_details(st, doc_id)
    except PaperlessError as exc:
        raise HTTPException(502, f"Paperless document #{doc_id} unavailable: {exc}") from exc


@router.get("/api/uncited-events")
async def get_uncited_events(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("citations_uncited_events") is None or refresh:
        st.caches["citations_uncited_events"] = await citations.uncited_events(st.gramps)
    return st.caches["citations_uncited_events"]


@router.get("/api/event/{handle}")
async def get_event(request: Request, handle: str):
    return await citations.event_detail(_state(request).gramps, handle)


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
        raise HTTPException(400, "no Anthropic API key")
    if not citations.has_house_style():
        raise HTTPException(
            400, "no citation style document configured")
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
    subject: str = ""
    transcript: str = ""
    urls: str = ""
    dump: str = ""
    media_handle: str | None = None
    event_context: str | None = None


@router.post("/api/compose-dump")
async def compose_dump(request: Request, body: DumpBody):
    st = _state(request)
    if not st.anthropic.configured:
        raise HTTPException(400, "no Anthropic API key")
    if not citations.has_house_style():
        raise HTTPException(
            400, "no citation style document configured")
    if st.caches.get("citations_context") is None:
        st.caches["citations_context"] = await citations.context(st.gramps)
    ctx = st.caches["citations_context"]
    media = None
    existing = None
    transcript, urls, dump = body.transcript, body.urls, body.dump
    if body.media_handle:
        media = await st.gramps.get_object("media", body.media_handle)
        existing = await _media_citations_cached(st, body.media_handle)
        doc_id = _paperless_id(media)
        if doc_id is not None and not (transcript.strip() or urls.strip() or dump.strip()):
            try:
                pl = await _paperless_details(st, doc_id)
            except PaperlessError as exc:
                raise HTTPException(
                    502, f"Paperless document #{doc_id} unavailable: {exc}") from exc
            transcript, urls, dump = pl["transcript"], pl["source_url"], pl["notes"]
    if not any(x.strip() for x in (body.subject, transcript, urls, dump)) \
            and not (body.event_context or "").strip():
        raise HTTPException(
            400, "nothing to draft from: the media has no Paperless transcript, source URL or notes")
    try:
        result = await citations.compose_from_dump(
            st.anthropic, dump, media, ctx["sources"], ctx["repositories"],
            body.event_context, subject=body.subject,
            transcript=transcript, urls=urls,
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
