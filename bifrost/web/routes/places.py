"""Places page + API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...modules import boundaries
from ..runs import record_run

router = APIRouter(prefix="/places", tags=["places"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def places_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "places.html", {})


@router.get("/api/list")
async def list_places(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("places") is None or refresh:
        st.caches["places"] = await boundaries.listing(
            st.gramps, st.cfg.places.boundaries_dir)
    return {"places": st.caches["places"],
            "gramps_url": st.cfg.sync_paperless.gramps_public_url}


class SetRelationBody(BaseModel):
    handle: str
    relation: str  # raw id or a full openstreetmap.org/relation/N URL


@router.post("/api/set-relation")
async def set_relation(request: Request, body: SetRelationBody):
    st = _state(request)
    raw = body.relation.strip()
    m = boundaries.RELATION_RE.search(raw)
    rid = int(m.group(1)) if m else (int(raw) if raw.isdigit() else None)
    if rid is None:
        raise HTTPException(400, "give a numeric relation id or an openstreetmap.org/relation/… URL")
    try:
        result = await boundaries.set_relation(st.gramps, body.handle, rid)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    st.caches.pop("places", None)
    return result


class GenerateBody(BaseModel):
    handle: str
    force: bool = False


@router.post("/api/generate")
async def generate(request: Request, body: GenerateBody):
    st = _state(request)
    if not st.cfg.places.osm_service_url:
        raise HTTPException(400, "no osm_service_url configured")
    try:
        result = await boundaries.generate_one(
            st.cfg.places.osm_service_url, body.handle, body.force)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    st.caches.pop("places", None)
    return result


class GenerateMissingBody(BaseModel):
    force: bool = False


@router.post("/api/generate-missing")
async def generate_missing(request: Request, body: GenerateMissingBody):
    st = _state(request)
    if not st.cfg.places.osm_service_url:
        raise HTTPException(400, "no osm_service_url configured")
    gen = boundaries.generate_missing(
        st.gramps, st.cfg.places.osm_service_url,
        st.cfg.places.boundaries_dir, force=body.force)
    run_id, events = await record_run(st.conn, "places.boundaries", gen)
    st.caches.pop("places", None)
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}
