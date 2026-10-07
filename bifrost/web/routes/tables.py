"""Tables page + API: grids over Paperless document pages"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ...core.clients.gemini import GeminiError
from ...core.clients.paperless import PaperlessError
from ...modules import tables

router = APIRouter(prefix="/tables", tags=["tables"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _state(request: Request):
    return request.app.state


async def _doc(st, doc_id: int) -> dict:
    try:
        return await st.paperless.get_document(doc_id)
    except PaperlessError as exc:
        if exc.status == 404:
            raise HTTPException(404, f"no Paperless document #{doc_id}") from exc
        raise HTTPException(502, f"Paperless document #{doc_id} unavailable: {exc}") from exc


def _no_page(exc: Exception) -> HTTPException:
    if isinstance(exc, PaperlessError):
        return HTTPException(502, f"Paperless unavailable: {exc}")
    return HTTPException(404, str(exc))


@router.get("")
async def tables_home(request: Request):
    return RedirectResponse(url="/#tables")


@router.get("/api/list")
async def list_tables(request: Request) -> dict:
    return {"items": tables.list_tables(_state(request).conn)}


@router.get("/api/documents")
async def search_documents(request: Request, q: str = "", limit: int = 10) -> list[dict]:
    """Title search; a number also finds that document id"""
    st = _state(request)
    q = q.strip()
    limit = max(1, min(limit, 30))
    found: list[dict] = []
    try:
        if q.lstrip("#").isdigit():
            try:
                found.append(await st.paperless.get_document(int(q.lstrip("#"))))
            except PaperlessError as exc:
                if exc.status != 404:
                    raise
        seen = {d["id"] for d in found}
        found += [d for d in await st.paperless.search_documents(q, limit) if d["id"] not in seen]
    except PaperlessError as exc:
        raise HTTPException(502, f"Paperless unavailable: {exc}") from exc
    return [{"id": d["id"], "title": d.get("title") or f"#{d['id']}",
             "created": d.get("created"), "mime": d.get("mime_type")} for d in found[:limit]]


@router.get("/api/thumb/{doc_id}")
async def thumb(request: Request, doc_id: int):
    try:
        data, mime = await _state(request).paperless.thumbnail(doc_id)
    except PaperlessError as exc:
        raise HTTPException(404, str(exc)[:200]) from exc
    return Response(data, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})


@router.get("/api/doc/{doc_id}")
async def doc_info(request: Request, doc_id: int) -> dict:
    st = _state(request)
    doc = await _doc(st, doc_id)
    title = doc.get("title") or f"#{doc_id}"
    tables.set_title(st.conn, doc_id, title)
    try:
        pages, error = await tables.pages(st.paperless, doc), ""
    except (tables.PageError, PaperlessError) as exc:
        pages, error = 0, str(exc)
    public = st.cfg.sync_paperless.public_url
    return {
        "id": doc_id, "title": title, "pages": pages, "error": error,
        "version": tables.version_key(doc),
        "tables": tables.table_pages(st.conn, doc_id),
        "paperless_url": f"{public}/documents/{doc_id}/details" if public else "",
        "transcribe": st.gemini.configured,
    }


@router.get("/api/doc/{doc_id}/page/{page}/image")
async def page_image(request: Request, doc_id: int, page: int, v: str = ""):
    st = _state(request)
    doc = await _doc(st, doc_id)
    try:
        data, mime = await tables.page_file(st.paperless, doc, page)
    except (tables.PageError, PaperlessError) as exc:
        raise _no_page(exc) from exc
    cache = ("private, max-age=31536000, immutable" if v == tables.version_key(doc)
             else "no-cache")
    return Response(data, media_type=mime, headers={"Cache-Control": cache})


@router.get("/api/doc/{doc_id}/page/{page}")
async def get_grid(request: Request, doc_id: int, page: int) -> dict:
    saved = tables.get_table(_state(request).conn, doc_id, page)
    return saved or {"grid": None, "rev": 0, "updated_at": None}


class GridBody(BaseModel):
    grid: dict | None = None
    rev: int = 0


@router.put("/api/doc/{doc_id}/page/{page}")
async def put_grid(request: Request, doc_id: int, page: int, body: GridBody) -> dict:
    """Save the page's table, or delete it when grid is null"""
    st = _state(request)
    try:
        if body.grid is None:
            tables.delete_table(st.conn, doc_id, page, body.rev)
            return {"grid": None, "rev": 0, "updated_at": None}
        grid = tables.normalize_grid(body.grid)
        title = None
        if body.rev == 0:
            try:
                title = (await st.paperless.get_document(doc_id)).get("title")
            except PaperlessError:
                pass
        return tables.save_table(st.conn, doc_id, page, grid, body.rev, title)
    except tables.GridError as exc:
        raise HTTPException(400, str(exc)) from exc
    except tables.Conflict as exc:
        raise HTTPException(409, "The table was changed in another window") from exc


class TranscribeBody(BaseModel):
    rows: list[str] | None = None


@router.post("/api/doc/{doc_id}/page/{page}/transcribe")
async def transcribe(request: Request, doc_id: int, page: int, body: TranscribeBody) -> dict:
    """Gemini fills the empty cells of the given rows, or of every row"""
    st = _state(request)
    if not st.gemini.configured:
        raise HTTPException(400, "no Gemini API key configured")
    saved = tables.get_table(st.conn, doc_id, page)
    if saved is None:
        raise HTTPException(404, "this page has no table")
    doc = await _doc(st, doc_id)
    try:
        img = await tables.page_pil(st.paperless, doc, page)
    except (tables.PageError, PaperlessError) as exc:
        raise _no_page(exc) from exc
    try:
        readings, errors = await tables.transcribe(
            st.gemini, img, saved["grid"], body.rows, st.cfg.gemini.thinking_budget)
    except GeminiError as exc:
        raise HTTPException(502, f"Gemini: {exc}") from exc
    current = tables.get_table(st.conn, doc_id, page)
    if current is None:
        raise HTTPException(409, "The table was deleted while Gemini read it")
    grid, filled = tables.merge_readings(current["grid"], readings)
    out = tables.save_table(st.conn, doc_id, page, grid, current["rev"]) if filled else current
    return {**out, "filled": filled, "errors": errors}


class NoteBody(BaseModel):
    x: float | None = None
    y: float | None = None
    text: str | None = None


@router.get("/api/doc/{doc_id}/page/{page}/notes")
async def get_notes(request: Request, doc_id: int, page: int) -> list[dict]:
    return tables.list_notes(_state(request).conn, doc_id, page)


@router.post("/api/doc/{doc_id}/page/{page}/notes")
async def add_note(request: Request, doc_id: int, page: int, body: NoteBody) -> dict:
    st = _state(request)
    title = None
    try:
        title = (await st.paperless.get_document(doc_id)).get("title")
    except PaperlessError:
        pass
    try:
        return tables.add_note(st.conn, doc_id, page, body.x, body.y, body.text, title)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/api/notes/{note_id}")
async def edit_note(request: Request, note_id: int, body: NoteBody) -> dict:
    try:
        note = tables.update_note(_state(request).conn, note_id, body.text, body.x, body.y)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if note is None:
        raise HTTPException(404, "no such note")
    return note


@router.delete("/api/notes/{note_id}")
async def remove_note(request: Request, note_id: int) -> dict:
    if not tables.delete_note(_state(request).conn, note_id):
        raise HTTPException(404, "no such note")
    return {"deleted": note_id}


@router.get("/api/doc/{doc_id}/page/{page}/export.csv")
async def export_csv(request: Request, doc_id: int, page: int) -> Response:
    saved = tables.get_table(_state(request).conn, doc_id, page)
    if saved is None:
        raise HTTPException(404, "this page has no table")
    name = f"paperless-{doc_id}-page-{page}.csv"
    return Response(tables.to_csv(saved["grid"]).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{doc_id}", response_class=HTMLResponse)
async def table_page(request: Request, doc_id: int):
    return templates.TemplateResponse(request, "table.html", {"doc_id": doc_id})
