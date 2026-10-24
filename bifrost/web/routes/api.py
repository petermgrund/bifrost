"""Read-only API v1: codes and an export of what only Bifrost holds"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ...modules import api, codes
from .codes import _urls

router = APIRouter(prefix="/api/v1", tags=["api v1"])
log = logging.getLogger("bifrost.api")


def _state(request: Request):
    return request.app.state


@router.get("/code/{code}")
async def get_code(request: Request, code: str) -> dict:
    """A code's entry in the Codes ledger"""
    st = _state(request)
    wanted = codes.normalize(code)
    try:
        media = await st.gramps.get_media_by_gramps_id(wanted) if wanted else None
        live = {wanted} if media else set()
    except Exception as exc:  # noqa: BLE001
        log.warning("api: Gramps media unavailable: %s", exc)
        media, live = None, None
    titles = {wanted: media["desc"]} if media and media.get("desc") else {}
    found = codes.rows(st.conn, live, _urls(st.cfg), only=[wanted], titles=titles) if wanted else []
    if not found or not api.known(found[0]):
        raise HTTPException(404, f"{wanted or code} isn't in Bifrost's ledger")
    return api.code(found[0])


@router.get("/export")
async def get_export(request: Request) -> JSONResponse:
    """Everything only Bifrost holds, as one JSON file"""
    st = _state(request)
    try:
        media = await st.gramps.media_descriptions()
    except Exception as exc:  # noqa: BLE001
        log.warning("api: Gramps media unavailable: %s", exc)
        media = None
    rows = codes.rows(st.conn, None if media is None else set(media), _urls(st.cfg), titles=media)
    name = f"bifrost-export-{date.today().isoformat()}.json"
    return JSONResponse(api.export(st.conn, rows),
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})
