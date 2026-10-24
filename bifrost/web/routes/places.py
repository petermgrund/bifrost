"""Places page + API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...modules import places
from ..runs import record_run

router = APIRouter(prefix="/places", tags=["places"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def places_page(request: Request):
    return RedirectResponse(url="/#other")


class ApplyBody(BaseModel):
    selected: list[str] | None = None


def _suggestions(request: Request) -> dict:
    return _state(request).caches.setdefault("osm_suggestions", {})


@router.get("/api/links/config")
async def links_config(request: Request) -> dict:
    return {"enabled": True}


@router.post("/api/links/preview")
async def links_preview(request: Request, body: ApplyBody = ApplyBody()):
    st = _state(request)
    gen = places.scan_links(st.gramps, _suggestions(request))
    run_id, events = await record_run(st.conn, "places.links.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/links/apply")
async def links_apply(request: Request, body: ApplyBody = ApplyBody()):
    st = _state(request)
    if not body.selected:
        raise HTTPException(400, "no places selected")
    gen = places.apply_links(st.gramps, set(body.selected), _suggestions(request))
    run_id, events = await record_run(st.conn, "places.links", gen)
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}
