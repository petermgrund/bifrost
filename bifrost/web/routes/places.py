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


# ---- links

class ApplyBody(BaseModel):
    selected: list[str] | None = None


def _suggestions(request: Request) -> dict:
    return _state(request).caches.setdefault("osm_suggestions", {})


@router.get("/api/list")
async def list_places(request: Request) -> list[dict]:
    """Places without an OSM relation for search"""
    rows = await boundaries.listing(_state(request).gramps, None)
    return [{"handle": r["handle"], "gramps_id": r["gramps_id"], "name": r["name"],
             "hierarchy": r["hierarchy"]} for r in rows if not r["osm_id"]]


@router.get("/api/links/config")
async def links_config(request: Request) -> dict:
    return {"enabled": True}


@router.post("/api/links/preview")
async def links_preview(request: Request, body: ApplyBody = ApplyBody()):
    st = _state(request)
    gen = boundaries.scan_links(st.gramps, st.cfg.places.boundaries_dir, _suggestions(request))
    run_id, events = await record_run(st.conn, "places.links.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/links/apply")
async def links_apply(request: Request, body: ApplyBody = ApplyBody()):
    st = _state(request)
    if not body.selected:
        raise HTTPException(400, "no places selected")
    gen = boundaries.apply_links(
        st.gramps, st.cfg.places.boundaries_dir, set(body.selected), _suggestions(request))
    run_id, events = await record_run(st.conn, "places.links", gen)
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}


class LinkBody(BaseModel):
    gramps_id: str
    relation: str
    replace: bool = True


@router.post("/api/set-relation")
async def set_relation(request: Request, body: LinkBody):
    """Link one place by hand"""
    st = _state(request)
    raw = body.relation.strip()
    m = boundaries.OSM_REF_RE.search(raw) or re.search(r"^(relation|way)/(\d+)$", raw)
    if m:
        kind, oid = m.group(1), int(m.group(2))
    elif raw.isdigit():
        kind, oid = "relation", int(raw)
    else:
        raise HTTPException(400, "give a relation id, relation/<id>, way/<id> or an openstreetmap.org URL")
    gid = body.gramps_id.strip().upper()
    place = await st.gramps.get_place_by_gramps_id(gid)
    if place is None:
        raise HTTPException(404, f"no Gramps place '{gid}'")
    had = boundaries.osm_ref(place)
    coords = None
    if not ((place.get("lat") or "").strip() and (place.get("long") or "").strip()):
        try:
            found = await boundaries.lookup_osm(kind, oid)
        except Exception:  # noqa: BLE001
            found = None
        if found and "lat" in found:
            coords = (found["lat"], found["lon"])
    try:
        await boundaries.write_place(
            st.gramps, place["handle"], osm=(kind, oid), coords=coords, replace=body.replace)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    boundary_error = None
    if st.cfg.places.boundaries_dir:
        try:
            await boundaries.generate_one(
                st.gramps, st.cfg.places.boundaries_dir, place["handle"], force=True)
        except Exception as exc:  # noqa: BLE001
            boundary_error = str(exc)[:200]
    return {"handle": place["handle"], "osm_type": kind, "osm_id": oid, "gramps_id": gid,
            "name": (place.get("name") or {}).get("value") or gid,
            "replaced": f"{had[0]} {had[1]}" if had else None,
            "coordinates": f"{coords[0]:.4f}, {coords[1]:.4f}" if coords else None,
            "boundary_error": boundary_error}


# ---- boundaries

def _boundaries_dir(request: Request):
    d = _state(request).cfg.places.boundaries_dir
    if not d:
        raise HTTPException(400, "no places.boundaries_dir configured")
    return d


@router.get("/api/config")
async def config(request: Request) -> dict:
    d = _state(request).cfg.places.boundaries_dir
    return {"enabled": bool(d), "boundaries_dir": str(d) if d else ""}


@router.post("/api/preview")
async def preview(request: Request, body: ApplyBody = ApplyBody()):
    st = _state(request)
    gen = boundaries.scan(st.gramps, _boundaries_dir(request))
    run_id, events = await record_run(st.conn, "places.boundaries.preview", gen)
    return {"run_id": run_id, "apply": False, "events": [e.__dict__ for e in events]}


@router.post("/api/apply")
async def apply(request: Request, body: ApplyBody = ApplyBody()):
    st = _state(request)
    gen = boundaries.generate_missing(
        st.gramps, _boundaries_dir(request),
        selected=set(body.selected) if body.selected is not None else None)
    run_id, events = await record_run(st.conn, "places.boundaries", gen)
    return {"run_id": run_id, "apply": True, "events": [e.__dict__ for e in events]}
