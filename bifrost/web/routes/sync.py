"""Sync everything from a source + the Paperless webhook"""

from __future__ import annotations

import asyncio
import email
import hmac
import json
import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Request

from ...core.clients import PaperlessError
from ...modules import check, ocr, sync_paperless
from ..runs import record_run

log = logging.getLogger("bifrost.sync")

router = APIRouter(prefix="/sync", tags=["sync"])


def _state(request: Request):
    return request.app.state


async def _everything(st, job: str, events) -> dict:
    _run_id, collected = await record_run(job, events)
    st.caches.clear()
    summary = next((e.data for e in collected if e.kind == "summary"), None) or {}
    return {"summary": summary,
            "events": [e.__dict__ for e in collected if e.kind == "error" or e.action == "failed"]}


@router.post("/api/paperless")
async def sync_documents(request: Request) -> dict:
    """Sync every tagged Paperless document"""
    st = _state(request)
    if st.paperless is None:
        raise HTTPException(503, "Paperless is not configured")
    return await _everything(st, "sync.paperless", check.documents(st.gramps, st.paperless, st.gemini, st.cfg))


@router.post("/api/paperless/ocr")
async def ocr_documents(request: Request) -> dict:
    st = _state(request)
    if st.paperless is None:
        raise HTTPException(503, "Paperless not configured")
    return await _everything(st, "ocr", ocr.run_with_sync(
        st.paperless, st.gramps, st.gemini, st.cfg.sync_paperless, st.cfg.gemini))


@router.post("/api/immich")
async def sync_photos(request: Request) -> dict:
    """Sync every tagged Immich photo and the faces on the synced ones"""
    st = _state(request)
    accounts = getattr(st, "immich_accounts", [])
    if not accounts:
        raise HTTPException(503, "Immich is not configured")
    return await _everything(st, "sync.immich", check.photos(st.gramps, accounts, st.cfg))


async def _webhook_fields(request: Request) -> dict:
    """What Paperless sent: the query string over a JSON, urlencoded or multipart body"""
    ctype = request.headers.get("content-type", "")
    body = await request.body()
    fields: dict = {}
    if "json" in ctype:
        try:
            payload = json.loads(body)
        except ValueError:
            payload = None
        fields = payload if isinstance(payload, dict) else {}
    elif "multipart" in ctype:
        msg = email.message_from_bytes(f"Content-Type: {ctype}\r\n\r\n".encode() + body)
        fields = {name: part.get_payload(decode=True).decode(errors="replace")
                  for part in msg.walk()
                  if (name := part.get_param("name", header="content-disposition"))
                  and not part.get_filename()}
    elif body:
        fields = dict(parse_qsl(body.decode(errors="replace")))
    return {**fields, **request.query_params}


async def _ocr_tagged(st, doc_id: int) -> dict | None:
    """The document when it carries the OCR tag"""
    cfg = st.cfg.sync_paperless
    if not cfg.ocr_tag:
        return None
    try:
        doc = await st.paperless.get_document(doc_id)
    except PaperlessError:
        return None
    tag_id = await st.paperless.resolve_tag_id(cfg.ocr_tag)
    return doc if tag_id and tag_id in (doc.get("tags") or []) else None


def _queue_webhook(st, doc_id: int) -> None:
    """Sync the one document after the response, one webhook at a time"""
    if not hasattr(st, "webhook_lock"):
        st.webhook_lock = asyncio.Lock()
        st.webhook_tasks = set()

    async def job():
        async with st.webhook_lock:
            try:
                gen = sync_paperless.sync(st.paperless, st.gramps, st.cfg.sync_paperless,
                                          apply=True, doc_ids=[doc_id])
                await record_run("sync.paperless.webhook", gen)
                doc = await _ocr_tagged(st, doc_id)
                if doc is not None:
                    gen = ocr.run_with_sync(st.paperless, st.gramps, st.gemini, st.cfg.sync_paperless,
                                            st.cfg.gemini, docs=[doc])
                    await record_run("ocr.webhook", gen)
                st.caches.clear()
            except Exception:
                log.exception("webhook sync of Paperless #%d failed", doc_id)

    task = asyncio.create_task(job())
    st.webhook_tasks.add(task)
    task.add_done_callback(st.webhook_tasks.discard)


@router.post("/api/paperless/webhook", status_code=202)
async def paperless_webhook(request: Request):
    """Paperless's workflow webhook: one document changed"""
    st = _state(request)
    token = st.cfg.sync_paperless.webhook_token
    if st.paperless is None or not token:
        raise HTTPException(404)
    given = request.headers.get("X-Bifrost-Token", "")
    if not hmac.compare_digest(given.encode(), token.encode()):
        raise HTTPException(403, "bad X-Bifrost-Token")
    fields = await _webhook_fields(request)
    raw = str(fields.get("doc_id", fields.get("id", ""))).strip()
    if not raw.isdecimal():
        raise HTTPException(400, "doc_id must be a Paperless document id")
    doc_id = int(raw)
    _queue_webhook(st, doc_id)
    return {"doc_id": doc_id, "queued": True}
