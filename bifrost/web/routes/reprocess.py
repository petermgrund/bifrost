"""Reprocess page + API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...modules import reprocess
from ..runs import record_run

router = APIRouter(prefix="/reprocess", tags=["reprocess"])


def _scan_tag(request: Request) -> str:
    """First of sync_tags by convention"""
    return request.app.state.cfg.sync_paperless.sync_tags[0]


def _check_mode(mode: str) -> None:
    if mode not in (reprocess.MODE_WIDEST, reprocess.MODE_NARROWEST):
        raise HTTPException(400, f"mode must be '{reprocess.MODE_WIDEST}'"
                                 f" or '{reprocess.MODE_NARROWEST}'")


@router.get("")
async def reprocess_page(request: Request):
    return RedirectResponse(url="/#reprocess")


@router.get("/api/config")
async def config(request: Request) -> dict:
    return {"enabled": True, "tag": _scan_tag(request)}


class ApplyBody(BaseModel):
    selected: list[str] | None = None
    mode: str = reprocess.MODE_WIDEST


def _doc_ids(selected: list[str] | None) -> list[int]:
    ids = []
    for key in selected or []:
        entity, _, raw = key.partition(":")
        if entity == "doc" and raw.isdigit():
            ids.append(int(raw))
    return ids


@router.post("/api/preview")
async def preview(request: Request, body: ApplyBody = ApplyBody()):
    st = request.app.state
    gen = reprocess.scan(st.paperless, _scan_tag(request))
    run_id, events = await record_run(st.conn, "reprocess.widths.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/apply")
async def apply(request: Request, body: ApplyBody):
    st = request.app.state
    _check_mode(body.mode)
    doc_ids = _doc_ids(body.selected)
    if not doc_ids:
        raise HTTPException(400, "no documents selected")
    gen = reprocess.run_batch(st.paperless, doc_ids, body.mode)
    run_id, events = await record_run(st.conn, "reprocess.widths", gen)
    st.caches.clear()
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}
