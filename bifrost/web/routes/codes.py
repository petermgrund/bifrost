"""Codes page + API: list and withdraw codes"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...core.clients.gramps import GrampsError
from ...modules import codes

router = APIRouter(prefix="/codes", tags=["codes"])
log = logging.getLogger("bifrost.codes")
MEDIA_KEYS = "gramps_id,desc,mime,change,attribute_list"


def _state(request: Request):
    return request.app.state


def _urls(cfg) -> codes.Urls:
    return codes.Urls(
        gramps=cfg.sync_paperless.gramps_public_url or cfg.sync_immich.gramps_public_url,
        paperless=cfg.sync_paperless.public_url,
        immich=cfg.sync_immich.public_url,
    )


async def _media(st) -> tuple[list[dict] | None, str | None]:
    """Every Gramps media object, or None with the reason when Gramps can't be read"""
    try:
        return await st.gramps.list_media(keys=MEDIA_KEYS), None
    except Exception as exc:  # noqa: BLE001
        log.warning("codes: Gramps media unavailable: %s", exc)
        return None, str(exc)[:200]


async def _documents(st) -> set[str] | None:
    """Every Paperless document id, or None when Paperless can't be read"""
    try:
        return {str(i) for i in await st.paperless.document_ids()}
    except Exception as exc:  # noqa: BLE001
        log.warning("codes: Paperless document ids unavailable: %s", exc)
        return None


async def _withdrawn(st) -> dict[str, dict]:
    try:
        return await codes.withdrawn(st.gramps)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"Gramps could not be read: {str(exc)[:200]}")


async def _item(st, code: str) -> dict | None:
    media = await st.gramps.get_media_by_gramps_id(code)
    found = codes.rows([media] if media else [], await _withdrawn(st), _urls(st.cfg), only=[code])
    return found[0] if found else None


@router.get("")
async def codes_page(request: Request):
    return RedirectResponse(url="/#codes")


@router.get("/api/list")
async def list_codes(request: Request, status: str = "", q: str = "") -> dict:
    """Every code with its status; ?status= and ?q= narrow the items"""
    st = _state(request)
    try:
        wanted = codes.status_filter(status)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    (media, gramps_error), documents, withdrawn = await asyncio.gather(
        _media(st), _documents(st), _withdrawn(st))
    items = codes.search(codes.rows(media or [], withdrawn, _urls(st.cfg), documents=documents), q)
    return {
        "gramps": "unknown" if media is None else "ok",
        "gramps_error": gramps_error,
        "counts": codes.counts(items),
        "items": [r for r in items if codes.matches(r, wanted)],
    }


class WithdrawBody(BaseModel):
    reason: str = ""


@router.post("/api/{code}/withdraw")
async def withdraw(request: Request, code: str, body: WithdrawBody) -> dict:
    st = _state(request)
    try:
        code = await codes.withdraw(st.gramps, code, body.reason)
    except codes.CodeError as exc:
        raise HTTPException(exc.status, exc.detail)
    except GrampsError as exc:
        raise HTTPException(502, str(exc)[:200])
    return {"item": await _item(st, code)}


@router.get("/api/{code}/thumbnail")
async def thumbnail(request: Request, code: str, size: int = 256):
    """The code's Gramps media thumbnail"""
    st = _state(request)
    code = codes.normalize(code)
    try:
        media = await st.gramps.get_media_by_gramps_id(code)
        if media is None:
            raise HTTPException(404, f"{code} is not in Gramps.")
        content, mime = await st.gramps.media_thumbnail(media["handle"], size)
    except GrampsError as exc:
        raise HTTPException(502, str(exc)[:200]) from exc
    return Response(content, media_type=mime, headers={"Cache-Control": "public, max-age=3600"})
