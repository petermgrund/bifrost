"""Tables page + API: grids over Paperless document pages"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ...core.clients.gemini import GeminiError
from ...core.clients.gramps import GrampsError
from ...core.clients.paperless import PaperlessError
from ...modules import codes, tables

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


def _pid(value) -> str:
    return codes.normalize(str(value)) if value else ""


def _code(st, doc: dict) -> str:
    """The document's Gramps ID, set once it is synced to Gramps"""
    field = st.cfg.sync_paperless.gramps_id_field_id
    return _pid(st.paperless.custom_field_value(doc, field) if field else None)


def _no_page(exc: Exception) -> HTTPException:
    if isinstance(exc, PaperlessError):
        return HTTPException(502, f"Paperless unavailable: {exc}")
    return HTTPException(404, str(exc))


@router.get("")
async def tables_home(request: Request):
    return RedirectResponse(url="/#tables")


@router.get("/api/list")
async def list_tables(request: Request) -> dict:
    st = _state(request)
    items = tables.list_tables(st.conn)
    field = st.cfg.sync_paperless.gramps_id_field_id
    values = {}
    if items and field:
        try:
            values = await st.paperless.custom_field_values(field, ids={t["doc_id"] for t in items})
        except PaperlessError:
            values = {}
    return {"items": [{**t, "pid": _pid(values.get(t["doc_id"]))} for t in items]}


@router.get("/api/documents")
async def search_documents(request: Request, q: str = "", limit: int = 10) -> list[dict]:
    """Documents synced to Gramps whose Gramps ID or title contains the query, Gramps ID matches first"""
    st = _state(request)
    q = q.strip()
    limit = max(1, min(limit, 30))
    field = st.cfg.sync_paperless.gramps_id_field_id
    if not field:
        return []
    try:
        if q and q.isalnum():
            by_pid, by_title = await asyncio.gather(
                st.paperless.search_documents(q, limit, field),
                st.paperless.search_documents(q, limit, with_field=field))
        else:
            by_pid, by_title = [], await st.paperless.search_documents(q, limit, with_field=field)
    except PaperlessError as exc:
        raise HTTPException(502, f"Paperless unavailable: {exc}") from exc
    found, seen = [], set()
    for d in by_pid + by_title:
        if d["id"] not in seen:
            seen.add(d["id"])
            found.append(d)

    return [{"id": d["id"], "title": d.get("title") or f"#{d['id']}", "pid": _code(st, d),
             "created": d.get("created"), "mime": d.get("mime_type")} for d in found[:limit]]


@router.get("/api/people")
async def find_people(request: Request, q: str = "", limit: int = 20) -> list[dict]:
    """Gramps people for a name or ID; recently changed people when the query is empty"""
    rules = tables.people_rules(q)
    try:
        found = await _state(request).gramps.find_people(
            rules, max(1, min(limit, 50)), "name" if rules else "-change")
    except GrampsError as exc:
        raise HTTPException(502, f"Gramps unavailable: {exc}") from exc
    return [tables.person_summary(p) for p in found]


@router.get("/api/people/lookup")
async def lookup_people(request: Request, handles: str = "") -> list[dict]:
    """The linked people's profiles; a person deleted from Gramps comes back as missing"""
    gramps = _state(request).gramps
    wanted = list(dict.fromkeys(h for h in handles.split(",") if tables.valid_handle(h)))[:200]
    gate = asyncio.Semaphore(8)

    async def one(handle: str) -> dict:
        async with gate:
            person = await gramps.person_profile(handle)
        return tables.person_summary(person) if person else {"handle": handle, "missing": True}

    try:
        return list(await asyncio.gather(*(one(h) for h in wanted)))
    except GrampsError as exc:
        raise HTTPException(502, f"Gramps unavailable: {exc}") from exc


@router.get("/api/people/{handle}/photo")
async def person_photo(request: Request, handle: str, size: int = 64):
    if not tables.valid_handle(handle):
        raise HTTPException(404, "no such person")
    try:
        found = await _state(request).gramps.person_photo(handle, max(16, min(size, 256)))
    except GrampsError as exc:
        raise HTTPException(502, f"Gramps unavailable: {exc}") from exc
    if found is None:
        raise HTTPException(404, "no picture")
    return Response(found[0], media_type=found[1], headers={"Cache-Control": "private, max-age=3600"})


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
        "code": _code(st, doc),
        "version": tables.version_key(doc),
        "tables": tables.table_pages(st.conn, doc_id),
        "paperless_url": f"{public}/documents/{doc_id}/details" if public else "",
        "gramps_url": st.cfg.sync_paperless.gramps_public_url or st.cfg.sync_immich.gramps_public_url,
        "transcribe": st.gemini.configured,
        **tables.doc_options(st.conn, doc_id),
    }


class OptionsBody(BaseModel):
    translations: bool


@router.put("/api/doc/{doc_id}/options")
async def put_options(request: Request, doc_id: int, body: OptionsBody) -> dict:
    return tables.set_doc_options(_state(request).conn, doc_id, body.translations)


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
            doc = await _doc(st, doc_id)
            if not _code(st, doc):
                raise HTTPException(403, f"Paperless document #{doc_id} isn't synced to Gramps")
            title = doc.get("title")
        return tables.save_table(st.conn, doc_id, page, grid, body.rev, title)
    except tables.GridError as exc:
        raise HTTPException(400, str(exc)) from exc
    except tables.Conflict as exc:
        raise HTTPException(409, "The table was changed in another window") from exc


@router.delete("/api/doc/{doc_id}/page/{page}")
async def delete_page(request: Request, doc_id: int, page: int) -> dict:
    """Delete the page's table and notes"""
    if not tables.delete_page(_state(request).conn, doc_id, page):
        raise HTTPException(404, "nothing is saved on this page")
    return {"deleted": True}


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


@router.get("/at/{pinpoint}")
async def open_pinpoint(request: Request, pinpoint: str):
    """Open the page a pinpoint points into, with its cells selected"""
    st = _state(request)
    pin = tables.parse_pinpoint(pinpoint)
    if pin is None:
        raise HTTPException(404, f"'{pinpoint}' is not a pinpoint")
    doc_id = await tables.find_doc(st.paperless, st.conn, st.cfg.sync_paperless.gramps_id_field_id, pin["code"])
    if doc_id is None:
        raise HTTPException(404, f"no Paperless document has the PID {pin['code']}")
    frag = tables.pinpoint_fragment(pin)
    return RedirectResponse(f"/tables/{doc_id}?page={pin['page']}" + (f"#{frag}" if frag else ""), status_code=302)


@router.get("/{doc_id}", response_class=HTMLResponse)
async def table_page(request: Request, doc_id: int):
    return templates.TemplateResponse(request, "table.html", {"doc_id": doc_id})
