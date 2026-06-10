"""Faces page + JSON API.

One mental model: links (People view) + per-face padding (Photos view).
The single bulk action is "apply pending"; everything else is direct
manipulation that applies immediately.
"""

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


# --- links CRUD (link changes invalidate the photo listing) ---

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
    result = faces.set_link(
        st.conn, body.gramps_handle, body.immich_person_id, body.label,
        st.cfg.faces.person_map_export,
    )
    st.caches.pop("photos", None)
    return result


@router.delete("/api/links/{gramps_handle}")
async def remove_link(request: Request, gramps_handle: str):
    st = _state(request)
    if not faces.delete_link(st.conn, gramps_handle, st.cfg.faces.person_map_export):
        raise HTTPException(404, "not found")
    st.caches.pop("photos", None)
    return faces.list_links(st.conn)


# --- thumbnails (proxied so the browser never needs Immich credentials) ---

@router.get("/api/thumb/person/{person_id}")
async def person_thumb(request: Request, person_id: str):
    content, ctype = await _state(request).immich.person_thumbnail(person_id)
    return Response(content, media_type=ctype, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/api/thumb/asset/{asset_id}")
async def asset_thumb(request: Request, asset_id: str, size: str = "thumbnail"):
    if size not in ("thumbnail", "preview"):
        raise HTTPException(400, "size must be thumbnail or preview")
    content, ctype = await _state(request).immich.asset_thumbnail(asset_id, size)
    return Response(content, media_type=ctype, headers={"Cache-Control": "public, max-age=3600"})


# --- photos view ---

@router.get("/api/photos")
async def photos(request: Request, refresh: bool = False):
    st = _state(request)
    if st.caches.get("photos") is None or refresh:
        st.caches["photos"] = await faces.photo_listing(st.gramps, st.immich, st.conn)
    return st.caches["photos"]


class FaceBody(BaseModel):
    gramps_handle: str
    asset_id: str
    pad: float


@router.post("/api/face")
async def set_face(request: Request, body: FaceBody):
    st = _state(request)
    try:
        result = await faces.apply_face(
            st.gramps, st.immich, st.conn, body.gramps_handle, body.asset_id, body.pad
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Patch the cached listing in place so the UI stays consistent without a
    # full (and slow) refresh.
    listing = st.caches.get("photos")
    if listing:
        for photo in listing["photos"]:
            if photo["asset_id"] != body.asset_id:
                continue
            for f in photo["faces"]:
                if f.get("gramps_handle") == body.gramps_handle:
                    f.update(result)
            photo["pending_count"] = sum(
                1 for f in photo["faces"] if f.get("status") in ("pending", "outdated")
            )
        listing["pending_total"] = sum(p["pending_count"] for p in listing["photos"])
    return result


@router.post("/api/apply-pending")
async def apply_pending(request: Request):
    st = _state(request)
    gen = faces.apply_pending(st.gramps, st.immich, st.conn)
    run_id, events = await record_run(st.conn, "faces.apply", gen)
    st.caches.pop("photos", None)
    return {"run_id": run_id, "events": [e.__dict__ for e in events]}
