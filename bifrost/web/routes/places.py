"""Places page + API"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...modules import boundaries
from ..runs import record_run

router = APIRouter(prefix="/places", tags=["places"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def places_page(request: Request):
    return RedirectResponse(url="/#places")


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
    relation: str
    replace: bool = False


@router.post("/api/set-relation")
async def set_relation(request: Request, body: SetRelationBody):
    st = _state(request)
    raw = body.relation.strip()
    m = boundaries.OSM_REF_RE.search(raw) or re.search(r"^(relation|way)/(\d+)$", raw)
    if m:
        kind, oid = m.group(1), int(m.group(2))
    elif raw.isdigit():
        kind, oid = "relation", int(raw)
    else:
        raise HTTPException(
            400, "give a relation id")
    try:
        result = await boundaries.set_relation(
            st.gramps, body.handle, kind, oid, replace=body.replace)
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
    if not st.cfg.places.boundaries_dir:
        raise HTTPException(400, "no places.boundaries_dir configured")
    try:
        result = await boundaries.generate_one(
            st.gramps, st.cfg.places.boundaries_dir, body.handle, body.force)
    except boundaries.BoundaryFetchError as exc:
        raise HTTPException(502, str(exc)) from exc
    st.caches.pop("places", None)
    return result


class GenerateMissingBody(BaseModel):
    force: bool = False


@router.post("/api/generate-missing")
async def generate_missing(request: Request, body: GenerateMissingBody):
    st = _state(request)
    if not st.cfg.places.boundaries_dir:
        raise HTTPException(400, "no places.boundaries_dir configured")
    gen = boundaries.generate_missing(
        st.gramps, st.cfg.places.boundaries_dir, force=body.force)
    run_id, events = await record_run(st.conn, "places.boundaries", gen)
    st.caches.pop("places", None)
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}
