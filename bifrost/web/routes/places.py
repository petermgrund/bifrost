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


async def _apply(request: Request, body: ApplyBody, job: str) -> dict:
    st = _state(request)
    if not body.selected:
        raise HTTPException(400, "no places selected")
    gen = places.apply_links(st.gramps, set(body.selected), _suggestions(request))
    run_id, events = await record_run(st.conn, job, gen)
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}


@router.get("/api/list")
async def list_places(request: Request) -> list[dict]:
    """Places without an OSM link, for the manual link's search"""
    rows = await places.listing(_state(request).gramps)
    return [{"handle": r["handle"], "gramps_id": r["gramps_id"], "name": r["name"],
             "hierarchy": r["hierarchy"]} for r in rows if not r["osm_id"]]


# ---- scan

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
    return await _apply(request, body, "places.links")


# ---- manual link

class ManualBody(BaseModel):
    gramps_id: str = ""
    relation: str = ""


@router.get("/api/manual/config")
async def manual_config(request: Request) -> dict:
    return {"enabled": True}


@router.post("/api/manual/preview")
async def manual_preview(request: Request, body: ManualBody):
    st = _state(request)
    osm = places.parse_osm(body.relation)
    if osm is None:
        raise HTTPException(400, "give a relation id, relation/<id>, way/<id> or an openstreetmap.org URL")
    gid = body.gramps_id.strip().upper()
    place = await st.gramps.get_place_by_gramps_id(gid)
    if place is None:
        raise HTTPException(404, f"no Gramps place '{gid}'")
    gen = places.scan_manual(st.gramps, place["handle"], osm, _suggestions(request))
    run_id, events = await record_run(st.conn, "places.manual.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/manual/apply")
async def manual_apply(request: Request, body: ApplyBody = ApplyBody()):
    return await _apply(request, body, "places.manual")
