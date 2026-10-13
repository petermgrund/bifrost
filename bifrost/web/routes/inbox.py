"""Inbox page + API: capture records during research, file them in Paperless and Gramps, list what isn't cited"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ...core.clients import GrampsError, PaperlessError
from ...modules import inbox, ocr, sync_paperless
from ...modules.citations import gramps_id_of
from ...modules.codes import normalize
from ..runs import record_run
from . import tables

router = APIRouter(prefix="/inbox", tags=["inbox"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

FILES = inbox.FileStore()
RUNNING: dict[int, asyncio.Task] = {}
CONSUME_POLL_S = 2.0
CONSUME_TIMEOUT_S = 600.0
RETRY_AFTER_S = 30.0
CITED_TTL_S = 15.0
SYNCED_TTL_S = 60.0
NOTE_FAILED = "The note didn't reach Paperless"


def _refused(exc: inbox.CaptureError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.get("", response_class=HTMLResponse)
async def inbox_page(request: Request):
    return templates.TemplateResponse(request, "inbox.html", {})


@router.get("/api/config")
async def config(request: Request) -> dict:
    st = request.app.state
    return {"transcribe": bool(st.cfg.sync_paperless.ocr_tag) and st.gemini.configured}


@router.post("/api/files")
async def add_file(request: Request, name: str = "") -> dict:
    """Hold one file for the capture card"""
    data = await request.body()
    if not data:
        raise HTTPException(400, "The file is empty")
    if len(data) > inbox.MAX_FILE:
        raise HTTPException(413, "The file is larger than 200 MB")
    try:
        return FILES.add(name, data)
    except inbox.CaptureError as exc:
        raise _refused(exc) from exc


@router.delete("/api/files/{fid}")
async def drop_file(fid: str) -> dict:
    FILES.drop([fid])
    return {"ok": True}


class ReadBody(BaseModel):
    text: str


@router.post("/api/read")
async def read(body: ReadBody) -> dict:
    """What a pasted clip says about the record"""
    return inbox.read_paste(body.text)


class CaptureBody(BaseModel):
    files: list[str]
    title: str = ""
    link: str = ""
    details: dict[str, str] = {}
    note: str = ""
    transcribe: bool = False
    pasted: str = ""


@router.post("/api/captures")
async def create(request: Request, body: CaptureBody) -> dict:
    st = request.app.state
    try:
        row = await inbox.capture(
            st.paperless, st.conn, st.cfg.sync_paperless, FILES, body.files, title=body.title, link=body.link,
            details=body.details, note=body.note, transcribe=body.transcribe, pasted=body.pasted)
    except inbox.CaptureError as exc:
        raise _refused(exc) from exc
    except PaperlessError as exc:
        raise HTTPException(502, f"Paperless refused the upload: {exc}") from exc
    _start(st, row["id"])
    return row


@router.get("/api/captures")
async def listing(request: Request, older: bool = False) -> dict:
    """Captures not yet cited, newest first, then the older uncited documents when asked"""
    st = request.app.state
    rows = inbox.open_captures(st.conn)
    for row in rows:
        if row["state"] in inbox.OPEN and row["id"] not in RUNNING and inbox.stale(row, RETRY_AFTER_S):
            _start(st, row["id"])
    cited = await _cited(st)
    items = []
    for row in rows:
        if cited is not None and row["gramps_id"] and normalize(row["gramps_id"]) in cited:
            inbox.update_capture(st.conn, row["id"], cited_at=inbox.now())
            continue
        items.append(inbox.public(row))
    if older:
        items += await _older(st, cited)
    return {"items": items}


@router.delete("/api/captures/{cid}")
async def remove(request: Request, cid: int) -> dict:
    if not inbox.remove_capture(request.app.state.conn, cid):
        raise HTTPException(404, "no such capture")
    return {"ok": True}


@router.post("/api/hidden/{doc_id}")
async def hide(request: Request, doc_id: int) -> dict:
    inbox.hide_doc(request.app.state.conn, doc_id)
    return {"ok": True}


@router.get("/api/thumb/{doc_id}")
async def thumb(request: Request, doc_id: int):
    return await tables.thumb(request, doc_id)


async def _cited(st) -> set[str] | None:
    """Gramps IDs of media some citation shows, kept for a few seconds; None when Gramps can't be read"""
    hit = st.caches.get("inbox.cited")
    if hit and time.monotonic() - hit[0] < CITED_TTL_S:
        return hit[1]
    try:
        found = {normalize(i) for i in await st.gramps.cited_media_ids()}
    except GrampsError:
        return None
    st.caches["inbox.cited"] = (time.monotonic(), found)
    return found


async def _older(st, cited: set[str] | None) -> list[dict]:
    """Synced Paperless documents that are not captures and whose media no citation shows, newest first"""
    cfg = st.cfg.sync_paperless
    if cited is None or not cfg.gramps_id_field_id:
        return []
    hit = st.caches.get("inbox.synced")
    if hit and time.monotonic() - hit[0] < SYNCED_TTL_S:
        docs = hit[1]
    else:
        try:
            docs = await st.paperless.documents_with_field(cfg.gramps_id_field_id, "id,title,added,custom_fields")
        except PaperlessError:
            return []
        st.caches["inbox.synced"] = (time.monotonic(), docs)
    skip = inbox.captured_docs(st.conn) | inbox.hidden_docs(st.conn)
    rows = []
    for doc in docs:
        pid = gramps_id_of(cfg, doc)
        if pid and doc["id"] not in skip and pid not in cited:
            rows.append(inbox.older_row(doc, pid))
    return rows


def _kept(error: str | None) -> str | None:
    """The part of a capture's error that outlives a step that worked: a note Paperless didn't take"""
    return error if error and error.startswith(NOTE_FAILED) else None


def _start(st, cid: int) -> None:
    if cid in RUNNING:
        return
    task = asyncio.create_task(_advance(st, cid))
    RUNNING[cid] = task
    task.add_done_callback(lambda _task: RUNNING.pop(cid, None))


async def _advance(st, cid: int) -> None:
    """Carry one capture from Paperless's queue to a Gramps media object, then through its transcription"""
    try:
        row = inbox.get_capture(st.conn, cid)
        if row is not None and row["state"] == "processing":
            row = await _consumed(st, row)
        if row is not None and row["state"] == "filed":
            row = await _synced(st, row)
        if row is not None and row["state"] == "transcribing":
            await _transcribed(st, row)
    except Exception as exc:  # noqa BLE001
        inbox.update_capture(st.conn, cid, error=str(exc)[:300] or type(exc).__name__)


async def _consumed(st, row):
    """Wait for Paperless to consume the upload, then leave the capture's note on the new document"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + CONSUME_TIMEOUT_S
    task = None
    while loop.time() < deadline:
        try:
            task = await st.paperless.task_status(row["task_id"])
        except PaperlessError:
            task = None
        if task and task.get("status") in ("SUCCESS", "FAILURE"):
            break
        await asyncio.sleep(CONSUME_POLL_S)
    else:
        return None
    cid = row["id"]
    if task["status"] == "FAILURE" or not task.get("related_document"):
        inbox.update_capture(st.conn, cid, state="failed", error=inbox.consume_error(task.get("result")))
        return None
    doc_id = int(task["related_document"])
    error = None
    if text := inbox.paperless_note(row["note"], row["link"], inbox.details_of(row)):
        try:
            await st.paperless.add_note(doc_id, text)
        except PaperlessError as exc:
            error = f"{NOTE_FAILED}: {exc}"[:300]
    inbox.update_capture(st.conn, cid, doc_id=doc_id, state="filed", error=error)
    return inbox.get_capture(st.conn, cid)


async def _synced(st, row):
    """Make the Gramps media for the capture's document with the Paperless sync"""
    cfg = st.cfg.sync_paperless
    cid, doc_id = row["id"], row["doc_id"]
    gen = sync_paperless.sync(st.paperless, st.gramps, st.conn, cfg, apply=True, single_doc_id=doc_id)
    _run_id, events = await record_run(st.conn, "inbox.sync", gen)
    made = next((e.gramps_id for e in events if e.kind == "item" and e.action == "created" and e.gramps_id), "")
    made = made or gramps_id_of(cfg, await st.paperless.get_document(doc_id))
    if not made:
        problem = next((e.detail for e in events if e.kind == "error" or e.action == "failed"), "")
        inbox.update_capture(st.conn, cid, error=f"Not in Gramps yet: {problem}"[:300] if problem else
                             "Not in Gramps yet")
        return None
    inbox.update_capture(st.conn, cid, gramps_id=made, state="transcribing" if row["transcribe"] else "synced",
                         error=_kept(row["error"]))
    st.caches.pop("inbox.synced", None)
    return inbox.get_capture(st.conn, cid)


async def _transcribed(st, row) -> None:
    """Have Gemini transcribe the capture's document and send the transcription to Gramps"""
    gen = ocr.run_with_sync(st.paperless, st.gramps, st.gemini, st.conn, st.cfg.sync_paperless, st.cfg.gemini,
                            selected={f"doc:{row['doc_id']}"})
    _run_id, events = await record_run(st.conn, "inbox.ocr", gen)
    problem = next((e.detail for e in events if e.kind == "error" or e.action == "failed"), "")
    inbox.update_capture(st.conn, row["id"], state="synced",
                         error=f"Transcription failed: {problem}"[:300] if problem else _kept(row["error"]))
