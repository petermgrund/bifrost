"""Photos page + API"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ...core import settings as ui_settings
from ...core.clients.immich import ImmichError
from ...modules import faces, photo_collections, photos, sync_immich
from ...modules.sync_immich import SyncError
from ..runs import record_run
from .sync import _accounts_or_503

router = APIRouter(prefix="/photos", tags=["photos"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
PLACES_KEY = "photos_places"


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
        "description_link": ui_settings.get_description_link(st.conn),
        "sync_tag": cfg.sync_tag,
        "note_tag": cfg.note_sync_tag,
        "place_prefix": cfg.place_tag_prefix,
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


class SettingsBody(BaseModel):
    description_link: bool


@router.post("/api/settings")
async def set_settings(request: Request, body: SettingsBody) -> dict:
    st = _state(request)
    ui_settings.set_description_link(st.conn, body.description_link)
    return _config(st)


@router.get("/api/search")
async def search(request: Request, q: str = "", mode: str = "recent", person: str = "",
                 page: int = 1) -> dict:
    st = _state(request)
    accounts = _accounts_or_503(request)
    if mode not in ("recent", "tagged", "synced"):
        raise HTTPException(400, "mode must be recent, tagged or synced")
    return await photos.search(accounts, st.conn, st.cfg.sync_immich, mode=mode, q=q.strip(),
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
        st.caches[PLACES_KEY] = await photos.places(st.gramps, st.cfg.sync_immich)
    return st.caches[PLACES_KEY]


async def _place_rows(request: Request) -> dict:
    try:
        return {r["gramps_id"]: r for r in await _places(request)}
    except Exception:  # noqa: BLE001
        return {}


@router.get("/api/places")
async def places(request: Request, refresh: bool = False) -> list[dict]:
    return await _places(request, refresh)


@router.get("/api/photo/{asset_id}")
async def photo(request: Request, asset_id: str) -> dict:
    st = _state(request)
    accounts = _accounts_or_503(request)
    try:
        return await photos.load(accounts, st.conn, st.cfg.sync_immich, asset_id,
                                 await _place_rows(request))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


class DateBody(BaseModel):
    value: str
    precision: str | None = None
    modifier: str | None = None
    quality: str | None = None


class SyncBody(BaseModel):
    media: bool = False
    title: bool = False
    date: bool = False
    note: bool = False


class PhotoBody(BaseModel):
    title: str = ""
    date: DateBody | None = None
    place_gramps_id: str | None = None
    notes: str = ""
    sync: SyncBody = SyncBody()


@router.put("/api/photo/{asset_id}")
async def save_photo(request: Request, asset_id: str, body: PhotoBody) -> dict:
    st = _state(request)
    accounts = _accounts_or_503(request)
    form = {"title": body.title, "notes": body.notes, "place_gramps_id": body.place_gramps_id,
            "date": dict(body.date) if body.date else None, "sync": dict(body.sync)}
    try:
        return await photos.save(accounts, st.conn, st.cfg.sync_immich, asset_id, form,
                                 ui_settings.get_description_link(st.conn),
                                 await _place_rows(request))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


async def _run_sync(request: Request, asset_id: str) -> dict:
    st = _state(request)
    if not st.cfg.sync_immich.enabled:
        raise HTTPException(503, "the Immich sync is disabled in this instance (sync.immich.enabled)")
    accounts = _accounts_or_503(request)
    gen = sync_immich.sync_one_asset(st.gramps, accounts, st.conn, st.cfg.sync_immich,
                                     asset_id, update=True)
    try:
        run_id, events = await record_run(st.conn, "photos.sync", gen)
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)
    for key in list(st.caches):
        if key != PLACES_KEY:
            st.caches.pop(key, None)
    summary = next((e for e in reversed(events) if e.kind == "summary"), None)
    photo_rec = await photos.load(accounts, st.conn, st.cfg.sync_immich, asset_id,
                                  await _place_rows(request))
    return {"run_id": run_id, "summary": summary.data if summary else {},
            "events": [e.__dict__ for e in events if e.kind == "item"], "photo": photo_rec}


@router.post("/api/photo/{asset_id}/sync")
async def sync_photo(request: Request, asset_id: str) -> dict:
    return await _run_sync(request, asset_id)


class VersionBody(BaseModel):
    asset_id: str


@router.post("/api/photo/{asset_id}/versions")
async def add_version(request: Request, asset_id: str, body: VersionBody) -> dict:
    st = _state(request)
    try:
        return await photos.add_version(_accounts_or_503(request), st.conn, st.cfg.sync_immich,
                                        asset_id, body.asset_id.strip(), await _place_rows(request))
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
            new_id, rec = await photos.upload_version(accounts, st.conn, st.cfg.sync_immich, asset_id,
                                                      filename, data, modified, await _place_rows(request))
        except SyncError as exc:
            raise HTTPException(exc.status, exc.detail)
    return {"asset_id": new_id, "photo": rec}


@router.post("/api/photo/{asset_id}/versions/{member_id}/match")
async def match_version(request: Request, asset_id: str, member_id: str) -> dict:
    st = _state(request)
    try:
        return await photos.match_member(_accounts_or_503(request), st.conn, st.cfg.sync_immich,
                                         asset_id, member_id, await _place_rows(request))
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
        new_main = await photos.promote(accounts, st.conn, st.cfg.sync_immich,
                                        st.gramps, asset_id, member_id, body.redraw_faces)
        photo_rec = await photos.load(accounts, st.conn, st.cfg.sync_immich, new_main,
                                      await _place_rows(request))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)
    if photo_rec["gramps"]:
        return await _run_sync(request, new_main)
    return {"run_id": None, "summary": {}, "events": [], "photo": photo_rec}


class LabelBody(BaseModel):
    label: str = ""


@router.put("/api/photo/{asset_id}/versions/{member_id}/label")
async def set_version_label(request: Request, asset_id: str, member_id: str, body: LabelBody) -> dict:
    st = _state(request)
    accounts = _accounts_or_503(request)
    try:
        primary, client = await photos._primary_and_client(accounts, asset_id)
        _versions, member_ids = await photos._stack_members(client, primary)
        if member_id != asset_id and member_id not in member_ids:
            raise SyncError(404, "that asset is not a version of this photo")
        await photos.set_version_label(accounts, st.conn, st.cfg.sync_immich, member_id, body.label)
        return await photos.load(accounts, st.conn, st.cfg.sync_immich, asset_id,
                                 await _place_rows(request))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


@router.delete("/api/photo/{asset_id}/versions/{member_id}")
async def remove_version(request: Request, asset_id: str, member_id: str) -> dict:
    st = _state(request)
    try:
        return await photos.remove_version(_accounts_or_503(request), st.conn, st.cfg.sync_immich,
                                          asset_id, member_id, await _place_rows(request))
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)


class CollectionBody(BaseModel):
    name: str
    description: str = ""


class ItemsBody(BaseModel):
    asset_ids: list[str]


def _collection_or_404(st, cid: int) -> dict:
    row = photo_collections.get(st.conn, cid)
    if row is None:
        raise HTTPException(404, f"no collection {cid}")
    return row


def _with_cover(row: dict) -> dict:
    cover = row.pop("cover", None)
    return {**row, "cover": f"/photos/api/thumb/{cover}" if cover else None}


@router.get("/api/collections")
async def list_collections(request: Request) -> list[dict]:
    return [_with_cover(c) for c in photo_collections.list_all(_state(request).conn)]


@router.post("/api/collections")
async def create_collection(request: Request, body: CollectionBody) -> dict:
    try:
        return photo_collections.create(_state(request).conn, body.name, body.description)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


async def _detail(request: Request, cid: int) -> dict:
    st = _state(request)
    row = {**_collection_or_404(st, cid), "max_slots": photo_collections.MAX_ITEMS}
    if not photo_collections.item_ids(st.conn, cid):
        return {**row, "items": []}
    accounts = _accounts_or_503(request)
    ids = await photos.fold_stacked_items(accounts, st.conn, cid)
    slots = photo_collections.slots(st.conn, cid)
    return {**row, "items": [{**c, "slot": slots[c["asset_id"]]}
                             for c in await photos.cards_for(accounts, st.conn, ids)]}


@router.get("/api/collections/{cid}")
async def get_collection(request: Request, cid: int) -> dict:
    return await _detail(request, cid)


@router.put("/api/collections/{cid}")
async def update_collection(request: Request, cid: int, body: CollectionBody) -> dict:
    st = _state(request)
    _collection_or_404(st, cid)
    try:
        photo_collections.update(st.conn, cid, body.name, body.description)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return await _detail(request, cid)


@router.delete("/api/collections/{cid}")
async def delete_collection(request: Request, cid: int) -> dict:
    st = _state(request)
    _collection_or_404(st, cid)
    photo_collections.delete(st.conn, cid)
    return {"deleted": cid}


@router.post("/api/collections/{cid}/items")
async def add_collection_items(request: Request, cid: int, body: ItemsBody) -> dict:
    st = _state(request)
    _collection_or_404(st, cid)
    ids = await photos.primaries_of(_accounts_or_503(request), [a.strip() for a in body.asset_ids if a.strip()])
    try:
        added = photo_collections.add_items(st.conn, cid, ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {**(await _detail(request, cid)), "added": added}


@router.delete("/api/collections/{cid}/items/{asset_id}")
async def remove_collection_item(request: Request, cid: int, asset_id: str) -> dict:
    st = _state(request)
    _collection_or_404(st, cid)
    photo_collections.remove_item(st.conn, cid, asset_id)
    return await _detail(request, cid)


class PositionBody(BaseModel):
    position: int


@router.put("/api/collections/{cid}/items/{asset_id}/position")
async def move_collection_item(request: Request, cid: int, asset_id: str, body: PositionBody) -> dict:
    st = _state(request)
    _collection_or_404(st, cid)
    slots = photo_collections.move_item(st.conn, cid, asset_id, body.position)
    if slots is None:
        raise HTTPException(404, "that photo is not in this collection")
    return {"id": cid, "slots": slots}


@router.get("/api/immich-albums")
async def immich_albums(request: Request) -> list[dict]:
    return await photos.list_albums(_browse(request))


class ImportBody(BaseModel):
    album_id: str


@router.post("/api/collections/import")
async def import_album(request: Request, body: ImportBody) -> dict:
    st = _state(request)
    accounts = _accounts_or_503(request)
    try:
        cid, added = await photos.import_album(accounts, _browse(request), st.conn, body.album_id.strip())
    except SyncError as exc:
        raise HTTPException(exc.status, exc.detail)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {**(await _detail(request, cid)), "added": added}
