"""Faces page + JSON API (port of the legacy person_linker_gui routes)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from ...core.clients.gramps import person_display_name
from ...modules import faces
from ..runs import record_run

router = APIRouter(prefix="/faces", tags=["faces"])


def _state(request: Request):
    return request.app.state


@router.get("")
async def faces_page(request: Request):
    from ..app import templates  # late import to avoid cycle

    return templates.TemplateResponse(request, "faces.html", {})


# --- people lists (cached; ?refresh=1 to refetch) ---

@router.get("/api/gramps-people")
async def gramps_people(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("gramps_people") is None or refresh:
        raw = await st.gramps.list_people(extend_media=True)
        st.caches["gramps_people"] = [
            {
                "handle": p["handle"],
                "name": person_display_name(p),
                "gramps_id": p.get("gramps_id", ""),
                "media_count": len(p.get("media_list", [])),
                "rect_count": sum(1 for mr in p.get("media_list", []) if mr.get("rect")),
            }
            for p in raw
        ]
    return st.caches["gramps_people"]


@router.get("/api/immich-people")
async def immich_people(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("immich_people") is None or refresh:
        raw = await st.immich.list_people()
        st.caches["immich_people"] = [
            {"id": p["id"], "name": p.get("name") or "", "is_hidden": p.get("isHidden", False)}
            for p in raw
        ]
    return st.caches["immich_people"]


# --- links CRUD ---

class LinkBody(BaseModel):
    gramps_handle: str
    immich_person_id: str
    label: str | None = None


@router.get("/api/links")
async def get_links(request: Request):
    return faces.list_links(_state(request).conn)


@router.post("/api/links")
async def create_link(request: Request, body: LinkBody):
    st = _state(request)
    return faces.set_link(
        st.conn, body.gramps_handle, body.immich_person_id, body.label,
        st.cfg.faces.person_map_export,
    )


@router.delete("/api/links/{gramps_handle}")
async def remove_link(request: Request, gramps_handle: str):
    st = _state(request)
    if not faces.delete_link(st.conn, gramps_handle, st.cfg.faces.person_map_export):
        raise HTTPException(404, "not found")
    return faces.list_links(st.conn)


# --- thumbnails (proxied so the browser never needs Immich credentials) ---

@router.get("/api/thumb/person/{person_id}")
async def person_thumb(request: Request, person_id: str):
    content, ctype = await _state(request).immich.person_thumbnail(person_id)
    return Response(content, media_type=ctype, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/api/thumb/asset/{asset_id}")
async def asset_thumb(request: Request, asset_id: str):
    content, ctype = await _state(request).immich.asset_thumbnail(asset_id)
    return Response(content, media_type=ctype, headers={"Cache-Control": "public, max-age=3600"})


# --- apply operations ---

class ApplyBody(BaseModel):
    dry_run: bool = True


@router.post("/api/sync")
async def sync_faces(request: Request, body: ApplyBody):
    st = _state(request)
    gen = faces.link_faces(st.gramps, st.immich, st.conn, apply=not body.dry_run)
    run_id, events = await record_run(st.conn, "faces.link", gen)
    return {"run_id": run_id, "dry_run": body.dry_run,
            "events": [e.__dict__ for e in events]}


@router.post("/api/repad")
async def repad_faces(request: Request, body: ApplyBody):
    st = _state(request)
    gen = faces.repad_faces(st.gramps, st.immich, st.conn, apply=not body.dry_run)
    run_id, events = await record_run(st.conn, "faces.repad", gen)
    return {"run_id": run_id, "dry_run": body.dry_run,
            "events": [e.__dict__ for e in events]}


# --- synced media browser + lock ---

@router.get("/api/synced-media")
async def synced_media(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("synced_media") is None or refresh:
        st.caches["synced_media"] = await faces.synced_media_listing(
            st.gramps, st.immich, st.conn
        )
    return st.caches["synced_media"]


class LockBody(BaseModel):
    asset_id: str
    locked: bool


@router.post("/api/lock")
async def lock_asset(request: Request, body: LockBody):
    st = _state(request)
    try:
        result = await faces.set_asset_lock(
            st.gramps, st.immich, st.conn, body.asset_id, body.locked
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    for row in st.caches.get("synced_media") or []:
        if row["immich_asset_id"] == body.asset_id:
            row["is_manual"] = body.locked
    return result
