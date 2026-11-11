"""Photos page + API"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ...core.clients.gramps import GrampsError
from ...core.clients.immich import ImmichError
from ...modules import faces, photos, sync_immich
from ...modules.sync_immich import SyncError
from ..runs import record_run
from .sync import _accounts_or_503

router = APIRouter(prefix="/photos", tags=["photos"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
PLACES_KEY = "photos_places"
PEOPLE_KEY = "person_links"
REGISTERED_KEY = "immich_registered"


def _state(request: Request):
    return request.app.state


@router.get("", response_class=HTMLResponse)
async def photos_page(request: Request):
    return templates.TemplateResponse(request, "photos.html", {})


def _config(st) -> dict:
    cfg = st.cfg.sync_immich
    accounts = getattr(st, "immich_accounts", [])
    return {
        "enabled": cfg.enabled and bool(accounts),
        "immich_url": cfg.public_url,
        "gramps_url": cfg.gramps_public_url,
        "sync_tag": cfg.sync_tag,
        "accounts": [getattr(c, "label", "") for c in accounts],
        "browse_accounts": list(cfg.photos_accounts),
    }


def _browse(request: Request) -> list:
    st = _state(request)
    try:
        return photos.browse_accounts(_accounts_or_503(request), st.cfg.sync_immich)
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


@router.get("/api/config")
async def config(request: Request) -> dict:
    return _config(_state(request))


async def _registered(request: Request) -> dict[str, str]:
    """Immich asset id -> Gramps media id, read from Gramps and kept until something changes"""
    st = _state(request)
    if st.caches.get(REGISTERED_KEY) is None:
        try:
            st.caches[REGISTERED_KEY] = await sync_immich.registered_map(st.gramps)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Gramps could not be read: {str(exc)[:200]}")
    return st.caches[REGISTERED_KEY]


@router.get("/api/search")
async def search(request: Request, q: str = "", mode: str = "recent", person: str = "",
                 page: int = 1) -> dict:
    accounts = _accounts_or_503(request)
    if mode not in ("recent", "synced"):
        raise HTTPException(400, "mode must be recent or synced")
    return await photos.search(accounts, await _registered(request), mode=mode, q=q.strip(),
                               person=person.strip(), page=max(1, page), browse=_browse(request))


@router.get("/api/thumb/{asset_id}")
async def thumb(request: Request, asset_id: str, size: str = "thumbnail"):
    last: ImmichError | None = None
    for client in _accounts_or_503(request):
        try:
            content, mime = await client.asset_thumbnail(asset_id, size)
        except ImmichError as exc:
            last = exc
            continue
        return Response(content, media_type=mime,
                        headers={"Cache-Control": "public, max-age=3600"})
    raise HTTPException(404 if last and last.status in (400, 404) else 502,
                        last.message if last else "no Immich account")


@router.get("/api/people")
async def people(request: Request) -> list[dict]:
    rows = await faces.merged_people(_browse(request))
    return [{"id": p["id"], "name": p["name"], "account_label": p["account_label"],
             "thumb": f"/faces/api/person-thumbnail/{p['id']}"}
            for p in rows if p["name"] and not p["is_hidden"]]


async def _places(request: Request, refresh: bool = False) -> list[dict]:
    st = _state(request)
    if refresh or st.caches.get(PLACES_KEY) is None:
        st.caches[PLACES_KEY] = await photos.places(st.gramps)
    return st.caches[PLACES_KEY]


async def _person_map(request: Request) -> dict[str, str]:
    st = _state(request)
    if st.caches.get(PEOPLE_KEY) is None:
        st.caches[PEOPLE_KEY] = await sync_immich.load_person_map(st.gramps)
    return st.caches[PEOPLE_KEY]


async def _place_rows(request: Request) -> dict:
    try:
        return {r["gramps_id"]: r for r in await _places(request)}
    except Exception:  # noqa: BLE001
        return {}


@router.get("/api/places")
async def places(request: Request, refresh: bool = False) -> list[dict]:
    return await _places(request, refresh)


async def _load(request: Request, asset_id: str) -> dict:
    st = _state(request)
    return await photos.load(st.gramps, _accounts_or_503(request), st.cfg.sync_immich, asset_id,
                             await _place_rows(request), await _person_map(request),
                             await _registered(request))


def _drop_caches(st) -> None:
    for key in list(st.caches):
        if key not in (PLACES_KEY, PEOPLE_KEY):
            st.caches.pop(key, None)


@router.get("/api/photo/{asset_id}")
async def photo(request: Request, asset_id: str) -> dict:
    try:
        return await _load(request, asset_id)
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


class DateBody(BaseModel):
    value: str
    precision: str | None = None
    modifier: str | None = None
    quality: str | None = None
    minus: int | None = None
    plus: int | None = None


class PhotoBody(BaseModel):
    title: str = ""
    date: DateBody | None = None
    place_gramps_id: str | None = None
    notes: str = ""
    links: list[str] = []
    change: int | None = None
    gramps_id: str | None = None


async def _recorded(request: Request, job: str, gen) -> dict:
    st = _state(request)
    try:
        run_id, events = await record_run(job, gen)
    except SyncError as exc:
        _drop_caches(st)
        raise HTTPException(exc.status, exc.detail)
    _drop_caches(st)
    summary = next((e for e in reversed(events) if e.kind == "summary"), None)
    return {"run_id": run_id, "summary": summary.data if summary else {},
            "events": [e.__dict__ for e in events if e.kind == "item"]}


@router.put("/api/photo/{asset_id}")
async def save_photo(request: Request, asset_id: str, body: PhotoBody) -> dict:
    """Save the form to the Gramps media object; the first save adds the photo to Gramps"""
    st = _state(request)
    if not st.cfg.sync_immich.enabled:
        raise HTTPException(503, "the Immich sync is disabled in this instance (sync.immich.enabled)")
    accounts = _accounts_or_503(request)
    form = {**body.model_dump(), "date": dict(body.date) if body.date else None}
    try:
        photos.validate_form(form)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    gen = photos.save(st.gramps, accounts, st.cfg.sync_immich, asset_id, form, await _registered(request))
    result = await _recorded(request, "photos.save", gen)
    return {**result, "photo": await _load(request, asset_id)}


async def _run_sync(request: Request, asset_id: str) -> dict:
    st = _state(request)
    if not st.cfg.sync_immich.enabled:
        raise HTTPException(503, "the Immich sync is disabled in this instance (sync.immich.enabled)")
    gen = sync_immich.sync_one_asset(st.gramps, _accounts_or_503(request), st.cfg.sync_immich, asset_id,
                                     update=True, person_map=await _person_map(request),
                                     registered=await _registered(request))
    result = await _recorded(request, "photos.sync", gen)
    return {**result, "photo": await _load(request, asset_id)}


@router.get("/api/photo/{asset_id}/pending")
async def pending(request: Request, asset_id: str) -> dict:
    """What a sync would change in Gramps for a photo already there"""
    st = _state(request)
    try:
        changes = await photos.pending_changes(st.gramps, _accounts_or_503(request), st.cfg.sync_immich,
                                               asset_id, await _person_map(request),
                                               await _registered(request))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)
    except (GrampsError, ImmichError) as exc:
        raise HTTPException(502, str(exc)[:200])
    return {"changes": changes}


class VersionBody(BaseModel):
    asset_id: str


@router.post("/api/photo/{asset_id}/versions")
async def add_version(request: Request, asset_id: str, body: VersionBody) -> dict:
    st = _state(request)
    try:
        return await photos.add_version(st.gramps, _accounts_or_503(request), st.cfg.sync_immich,
                                        asset_id, body.asset_id.strip(), await _place_rows(request),
                                        await _registered(request))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


@router.post("/api/photo/{asset_id}/versions/upload")
async def upload_version(request: Request, asset_id: str, filename: str, modified: str = "") -> dict:
    st = _state(request)
    accounts = _accounts_or_503(request)
    with tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024) as data:
        async for chunk in request.stream():
            data.write(chunk)
        data.seek(0)
        try:
            new_id, rec = await photos.upload_version(st.gramps, accounts, st.cfg.sync_immich,
                                                      asset_id, filename, data, modified,
                                                      await _place_rows(request),
                                                      await _registered(request))
        except SyncError as exc:
            raise HTTPException(exc.status, exc.detail)
    return {"asset_id": new_id, "photo": rec}


@router.post("/api/photo/{asset_id}/versions/{member_id}/match")
async def match_version(request: Request, asset_id: str, member_id: str) -> dict:
    st = _state(request)
    try:
        return await photos.match_member(st.gramps, _accounts_or_503(request), st.cfg.sync_immich,
                                         asset_id, member_id, await _place_rows(request),
                                         await _registered(request))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


class PromoteBody(BaseModel):
    redraw_faces: bool = True


@router.post("/api/photo/{asset_id}/versions/{member_id}/promote")
async def promote_version(request: Request, asset_id: str, member_id: str,
                          body: PromoteBody = PromoteBody()) -> dict:
    st = _state(request)
    accounts = _accounts_or_503(request)
    try:
        new_main = await photos.promote(accounts, st.cfg.sync_immich, st.gramps, asset_id, member_id,
                                        body.redraw_faces, await _registered(request))
        photo_rec = await _load(request, new_main)
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)
    if photo_rec["gramps"]:
        return await _run_sync(request, new_main)
    return {"run_id": None, "summary": {}, "events": [], "photo": photo_rec}


class LabelBody(BaseModel):
    label: str = ""


@router.put("/api/photo/{asset_id}/versions/{member_id}/label")
async def set_version_label(request: Request, asset_id: str, member_id: str, body: LabelBody) -> dict:
    accounts = _accounts_or_503(request)
    try:
        primary, client = await photos._primary_and_client(accounts, asset_id)
        _versions, member_ids = await photos._stack_members(client, primary)
        if member_id != asset_id and member_id not in member_ids:
            raise SyncError(404, "that asset is not a version of this photo")
        await photos.set_version_label(accounts, member_id, body.label)
        return await _load(request, asset_id)
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


@router.delete("/api/photo/{asset_id}/versions/{member_id}")
async def remove_version(request: Request, asset_id: str, member_id: str) -> dict:
    st = _state(request)
    try:
        return await photos.remove_version(st.gramps, _accounts_or_503(request), st.cfg.sync_immich,
                                          asset_id, member_id, await _place_rows(request),
                                          await _registered(request))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)
