"""Media API: list, delete and merge the media Bifrost added to Gramps"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ...core.clients.gramps import GrampsError
from ...modules import codes, media

router = APIRouter(prefix="/media", tags=["media"])
log = logging.getLogger("bifrost.media")
MEDIA_KEYS = "gramps_id,desc,mime,change,date,attribute_list"


def _state(request: Request):
    return request.app.state


def _urls(cfg) -> codes.Urls:
    return codes.Urls(
        gramps=cfg.gramps.public_url,
        paperless=cfg.sync_paperless.public_url,
        immich=cfg.sync_immich.public_url,
    )


async def _documents(st) -> set[str] | None:
    """Every Paperless document id, or None when Paperless can't be read"""
    if st.paperless is None:
        return None
    try:
        return {str(i) for i in await st.paperless.document_ids()}
    except Exception as exc:  # noqa: BLE001
        log.warning("Paperless document ids unavailable: %s", exc)
        return None


@router.get("/api/list")
async def list_media(request: Request) -> dict:
    """Every media object that came from Paperless or Immich"""
    st = _state(request)

    async def gramps_media():
        try:
            return await st.gramps.list_media(keys=MEDIA_KEYS)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(503, f"Gramps could not be read: {str(exc)[:200]}")

    found, documents = await asyncio.gather(gramps_media(), _documents(st))
    items = codes.rows(found, _urls(st.cfg), documents=documents)
    return {"items": items}


async def _changed(st, action) -> dict:
    try:
        result = await action
    except codes.CodeError as exc:
        raise HTTPException(exc.status, exc.detail)
    except GrampsError as exc:
        raise HTTPException(502, str(exc)[:200])
    st.caches.clear()
    return result


@router.delete("/api/{code}")
async def delete(request: Request, code: str) -> dict:
    """Delete the media object from Gramps and stop syncing its document or photo"""
    st = _state(request)
    return await _changed(st, media.delete(st.gramps, st.paperless, getattr(st, "immich_accounts", []),
                                           st.cfg, code))


class MergeBody(BaseModel):
    into: str = ""


@router.post("/api/{code}/merge")
async def merge(request: Request, code: str, body: MergeBody) -> dict:
    """Move what shows this media object to another one, note its ID there, then delete it"""
    st = _state(request)
    return await _changed(st, media.merge(st.gramps, st.paperless, getattr(st, "immich_accounts", []),
                                          st.cfg, code, body.into))


@router.get("/api/{code}/thumbnail")
async def thumbnail(request: Request, code: str, size: int = 256):
    """The code's Gramps media thumbnail"""
    st = _state(request)
    code = codes.normalize(code)
    try:
        found = await st.gramps.get_media_by_gramps_id(code)
        if found is None:
            raise HTTPException(404, f"{code} is not in Gramps.")
        content, mime = await st.gramps.media_thumbnail(found["handle"], size)
    except GrampsError as exc:
        raise HTTPException(502, str(exc)[:200]) from exc
    return Response(content, media_type=mime, headers={"Cache-Control": "public, max-age=3600"})
