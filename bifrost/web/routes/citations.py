"""Citations wizard: build a Source and Citation by the style guide, create them in Gramps, file the scan"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ...core.clients import GrampsError, PaperlessError
from ...modules import citations
from . import tables

router = APIRouter(prefix="/citations", tags=["citations"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _failed(exc: Exception) -> HTTPException:
    if isinstance(exc, citations.CitationError):
        return HTTPException(exc.status, str(exc))
    if isinstance(exc, PaperlessError) and exc.status == 404:
        return HTTPException(404, "no such Paperless document")
    return HTTPException(502, str(exc)[:500])


@router.get("", response_class=HTMLResponse)
async def citations_page(request: Request):
    return templates.TemplateResponse(request, "citations.html", {})


@router.get("/api/context")
async def get_context(request: Request) -> dict:
    st = request.app.state
    try:
        ctx = await citations.context(st.gramps, st.paperless, st.conn)
    except (GrampsError, PaperlessError) as exc:
        raise _failed(exc) from exc
    return {**ctx, "gramps_url": st.cfg.sync_paperless.gramps_public_url,
            "paperless_url": st.cfg.sync_paperless.public_url}


@router.get("/api/documents")
async def documents(request: Request, q: str = "", limit: int = 10) -> list[dict]:
    """Paperless documents synced to Gramps, found as the Tables picker finds them"""
    return await tables.search_documents(request, q, limit)


@router.get("/api/thumb/{doc_id}")
async def thumb(request: Request, doc_id: int):
    return await tables.thumb(request, doc_id)


@router.get("/api/doc/{doc_id}")
async def get_document(request: Request, doc_id: int) -> dict:
    st = request.app.state
    try:
        return await citations.document(st.gramps, st.paperless, st.cfg.sync_paperless, doc_id)
    except (citations.CitationError, GrampsError, PaperlessError) as exc:
        raise _failed(exc) from exc


class RepositoryBody(BaseModel):
    handle: str


class SourceBody(BaseModel):
    handle: str | None = None
    title: str = ""
    author: str = ""
    abbrev: str = ""
    pubinfo: str = ""
    call_number: str = ""
    repository: RepositoryBody | None = None


class CitationBody(BaseModel):
    page: str
    confidence: str
    frn: str
    srn: str


class ScanBody(BaseModel):
    title: str = ""
    document_type: int | None = None
    correspondent: int | None = None
    date_meaning: str | None = None
    source_url: str = ""


class InputsBody(BaseModel):
    type: str
    values: dict[str, str] = {}


class CreateBody(BaseModel):
    doc_id: int
    source: SourceBody
    citation: CitationBody
    scan: ScanBody | None = None
    inputs: InputsBody | None = None


@router.post("/api/create")
async def create(request: Request, body: CreateBody) -> dict:
    st = request.app.state
    try:
        result = await citations.create(
            st.gramps, st.paperless, st.cfg.sync_paperless, body.doc_id, body.source.model_dump(),
            body.citation.model_dump(), body.scan.model_dump() if body.scan else None)
    except (citations.CitationError, GrampsError, PaperlessError) as exc:
        raise _failed(exc) from exc
    if body.inputs:
        citations.remember(st.conn, result["source"]["handle"], body.inputs.type, body.inputs.values)
    return result
