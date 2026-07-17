"""Photos — browse Immich assets, edit gda.date / gda.gramps KV metadata,
and pair recto/verso scans. (Formerly the standalone urd app; folded in
2026-07-15. Syncing to Gramps happens on the Sync section, routes/sync.py.)

All Immich HTTP goes through core/clients/immich.py; the KV value shapes are
the core/gda contract. Immich is an optional integration — every route here
answers 503 when the immich section is unconfigured.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from ...core.clients import ImmichClient
from ...core.clients.immich import ImmichError, valid_uuid
from ...core.gda import dates, scan

log = logging.getLogger("bifrost.photos")

router = APIRouter(prefix="/photos", tags=["photos"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

THUMB_SIZES = {"thumbnail", "preview"}

ALBUM_IDS_KEY = "photos.album_ids"


def _state(request: Request):
    return request.app.state


def _immich(request: Request) -> ImmichClient:
    client = getattr(_state(request), "immich", None)
    if client is None:
        raise HTTPException(503, "Immich is not configured (immich.base_url/api_key)")
    return client


# -- album whitelist (app_settings; was urd's data/settings.json) --------------


def load_album_ids(conn: sqlite3.Connection) -> list[str]:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key=?", (ALBUM_IDS_KEY,)
    ).fetchone()
    if row is None:
        return []
    try:
        ids = json.loads(row["value"])
    except ValueError:
        log.warning("app_settings %s is corrupt — treating as empty", ALBUM_IDS_KEY)
        return []
    if not isinstance(ids, list):
        return []
    return [i for i in ids if isinstance(i, str)]


def save_album_ids(conn: sqlite3.Connection, ids: list[str]) -> None:
    with conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (ALBUM_IDS_KEY, json.dumps(ids)),
        )


# -- Immich server version (lazy, cached) --------------------------------------


async def _immich_version(request: Request) -> str:
    """Cached server version; checked lazily because Immich is optional and
    must not block app startup. Warns once when the major drifts from v3
    (the metadata endpoints this page trusts are v3-Stable)."""
    caches = _state(request).caches
    cached = caches.get("photos_immich_version")
    if cached:
        return cached
    try:
        v = await _immich(request).server_version()
        version = f"{v['major']}.{v['minor']}.{v['patch']}"
        if v["major"] != 3:
            log.warning(
                "the Photos page was written against Immich v3; server reports %s — "
                "verify the metadata endpoints before trusting writes.", version,
            )
    except (ImmichError, HTTPException, KeyError, TypeError, ValueError) as exc:
        log.warning("could not read Immich server version: %r", exc)
        return "unknown"
    caches["photos_immich_version"] = version
    return version


def _summary(asset: dict, kv: dict | None, cfg, stacks: dict | None = None) -> dict:
    exif = asset.get("exifInfo") or {}
    # v3.0.1 search results report stack: null even for stacked assets
    # (verified live) — listings pass the /stacks map as a fallback.
    stack = asset.get("stack") or (stacks or {}).get(asset["id"])
    # kv None = the metadata FETCH failed (distinct from "no metadata") —
    # the frontend must not present that as editable-blank.
    kv_error = kv is None
    kv = kv or {}
    return {
        "id": asset["id"],
        "name": asset.get("originalFileName") or "",
        "takenAt": exif.get("dateTimeOriginal") or asset.get("localDateTime") or asset.get("fileCreatedAt"),
        "stack": {
            "id": stack["id"],
            "primary": stack.get("primaryAssetId") == asset["id"],
            "count": stack.get("assetCount"),
        } if stack else None,
        "date": kv.get(cfg.date_key),
        "scan": kv.get(cfg.scan_key),
        "gramps": kv.get(cfg.gramps_key),
        # {"verso": id} on a recto, {"recto": id} on a verso, else None
        "pair": kv.get(cfg.verso_key),
        "kvError": kv_error,
    }


_STACKS_TTL = 60.0


async def _stacks_map(request: Request) -> dict[str, dict]:
    """{asset_id: {"id", "primaryAssetId", "assetCount"}} for every stacked
    asset, briefly cached — the one complete source of stack membership."""
    caches = _state(request).caches
    now = time.monotonic()
    hit = caches.get("photos_stacks")
    if hit and hit[0] > now:
        return hit[1]
    mapping: dict[str, dict] = {}
    for s in await _immich(request).list_stacks():
        members = s.get("assets") or []
        for a in members:
            mapping[a["id"]] = {
                "id": s["id"],
                "primaryAssetId": s.get("primaryAssetId"),
                "assetCount": len(members),
            }
    caches["photos_stacks"] = (now + _STACKS_TTL, mapping)
    return mapping


# -- page ----------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
async def photos_page(request: Request):
    cfg = _state(request).cfg
    return templates.TemplateResponse(
        request,
        "photos.html",
        {"immich_url": cfg.sync_immich.public_url or cfg.immich.base_url},
    )


# -- vocab / config for the frontend ------------------------------------------


@router.get("/api/config")
async def api_config(request: Request):
    cfg = _state(request).cfg.sync_immich
    return {
        "dateKey": cfg.date_key,
        "scanKey": cfg.scan_key,
        "grampsKey": cfg.gramps_key,
        "modifiers": list(dates.MODIFIERS),
        "qualities": list(dates.QUALITIES),
        "months": list(dates.MONTHS),
        "roles": [{"value": k, "label": v} for k, v in scan.ROLES.items()],
        "immichVersion": await _immich_version(request),
    }


# -- settings -------------------------------------------------------------------


@router.get("/api/settings")
async def api_get_settings(request: Request):
    return {"albumIds": load_album_ids(_state(request).conn)}


@router.put("/api/settings")
async def api_put_settings(request: Request, payload: dict = Body(...)):
    ids = payload.get("albumIds")
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise HTTPException(422, "albumIds must be a list of album ids")
    bad = [i for i in ids if not valid_uuid(i)]
    if bad:
        raise HTTPException(422, f"invalid album ids: {bad[:3]}")
    deduped = list(dict.fromkeys(ids))
    save_album_ids(_state(request).conn, deduped)
    _state(request).caches.pop("photos_merge", None)
    return {"albumIds": deduped}


# -- browse -------------------------------------------------------------------


@router.get("/api/albums")
async def api_albums(request: Request):
    albums = await _immich(request).albums()
    albums.sort(key=lambda a: (a.get("albumName") or "").lower())
    enabled = set(load_album_ids(_state(request).conn))
    return [
        {
            "id": a["id"],
            "name": a.get("albumName") or "(unnamed)",
            "count": a.get("assetCount", 0),
            "enabled": a["id"] in enabled,
        }
        for a in albums
    ]


@router.get("/api/people")
async def api_people(request: Request):
    people = await _immich(request).people()
    named = [{"id": p["id"], "name": (p.get("name") or "").strip()} for p in people]
    named = [p for p in named if p["name"]]
    named.sort(key=lambda p: p["name"].lower())
    return named


# "All albums" with a configured album whitelist needs a UNION of albums, but
# Immich's search treats multiple albumIds as an INTERSECTION (verified on
# v3.0.1: two disjoint albums together -> 0 results). So the merged view fans
# out one search per enabled album and merges here, behind a short-lived cache.
_MERGE_TTL = 60.0
_ALBUM_ASSET_CAP = 5000  # per album, safety valve

_sort_key = (
    lambda a: (a.get("exifInfo") or {}).get("dateTimeOriginal")
    or a.get("localDateTime")
    or a.get("fileCreatedAt")
    or ""
)


async def _fetch_album_all(
    immich: ImmichClient, album_id: str, name: str | None, person: str | None,
    order: str,
) -> list[dict]:
    items: list[dict] = []
    page: int | None = 1
    while page and len(items) < _ALBUM_ASSET_CAP:
        try:
            r = await immich.search_assets(
                page=page, size=200, album_id=album_id, person_id=person,
                filename=name, order=order,
            )
        except ImmichError as exc:
            log.warning("merged listing: album %s failed: %s", album_id, exc)
            break
        items.extend(r["items"])
        page = r["nextPage"]
    return items


async def _merged_page(
    request: Request, album_ids: list[str], page: int, size: int,
    name: str | None, person: str | None, order: str,
) -> tuple[list[dict], int | None]:
    cache: dict = _state(request).caches.setdefault("photos_merge", {})
    key = (tuple(album_ids), name or "", person or "", order)
    now = time.monotonic()
    hit = cache.get(key)
    if hit and hit[0] > now:
        merged = hit[1]
    else:
        immich = _immich(request)
        lists = await asyncio.gather(
            *(_fetch_album_all(immich, a, name, person, order) for a in album_ids)
        )
        seen: set[str] = set()
        merged = []
        for asset in (x for lst in lists for x in lst):
            if asset["id"] not in seen:
                seen.add(asset["id"])
                merged.append(asset)
        merged.sort(key=_sort_key, reverse=order == "desc")
        cache.clear()  # one active view at a time keeps this tiny
        cache[key] = (now + _MERGE_TTL, merged)
    start = (page - 1) * size
    next_page = page + 1 if start + size < len(merged) else None
    return merged[start:start + size], next_page, len(merged)


@router.get("/api/assets")
async def api_assets(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(60, ge=1, le=200),
    album: str | None = None,
    person: str | None = None,
    name: str | None = None,
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    immich = _immich(request)
    cfg = _state(request).cfg.sync_immich
    enabled = load_album_ids(_state(request).conn)

    # total is known only for the merged view (Immich search reports no
    # usable grand total — its "total" is per-page, verified on v3.0.1);
    # the frontend falls back to album counts or a bare page number.
    total = None
    if not album and enabled:
        items, next_page, total = await _merged_page(
            request, enabled, page, size, name, person, order
        )
    else:
        result = await immich.search_assets(
            page=page, size=size, album_id=album, person_id=person,
            filename=name, order=order,
        )
        items, next_page = result["items"], result["nextPage"]

    kv_by_id = await immich.get_metadata_many([a["id"] for a in items])
    stacks = await _stacks_map(request)
    return {
        "items": [_summary(a, kv_by_id.get(a["id"]), cfg, stacks) for a in items],
        "nextPage": next_page,
        "total": total,
    }


@router.get("/api/assets/{asset_id}")
async def api_asset(request: Request, asset_id: str):
    immich = _immich(request)
    cfg = _state(request).cfg.sync_immich
    asset = await immich.get_asset(asset_id)
    kv = await immich.get_metadata(asset_id)

    stack_children = []
    stack = asset.get("stack") or {}
    if stack.get("id"):
        stack_detail = await immich.get_stack(stack["id"])
        child_assets = stack_detail.get("assets") or []
        detail_map = {
            c["id"]: {
                "id": stack_detail["id"],
                "primaryAssetId": stack_detail.get("primaryAssetId"),
                "assetCount": len(child_assets),
            }
            for c in child_assets
        }
        child_kv = await immich.get_metadata_many([c["id"] for c in child_assets])
        stack_children = [
            _summary(c, child_kv.get(c["id"]), cfg, detail_map)
            for c in child_assets
            if c["id"] != asset_id
        ]

    exif = asset.get("exifInfo") or {}
    return {
        **_summary(asset, kv, cfg),
        "people": [p.get("name") for p in (asset.get("people") or []) if p.get("name")],
        "description": exif.get("description") or "",
        # the editor redirects non-primary members here — metadata lives on
        # the stack's main image
        "stackPrimaryId": stack.get("primaryAssetId"),
        "stackChildren": stack_children,
    }


@router.get("/thumb/{asset_id}")
async def thumb(request: Request, asset_id: str, size: str = "thumbnail"):
    if size not in THUMB_SIZES:
        raise HTTPException(422, "size must be thumbnail or preview")
    content, media_type = await _immich(request).thumbnail(asset_id, size)
    # The app-wide middleware leaves pre-set Cache-Control alone — thumbs are
    # immutable enough to spare Immich a re-fetch per grid render.
    return Response(content, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


# -- date editing --------------------------------------------------------------


@router.post("/api/date/preview")
async def api_date_preview(payload: dict = Body(...)):
    try:
        normalized = dates.validate(payload)
    except dates.DateError as exc:
        return {"error": str(exc)}
    return {"display": normalized["display"], "sort": normalized["sort"]}


@router.put("/api/assets/{asset_id}/date")
async def api_put_date(request: Request, asset_id: str, payload: dict = Body(...)):
    try:
        normalized = dates.validate(payload)
    except dates.DateError as exc:
        raise HTTPException(422, str(exc))
    cfg = _state(request).cfg.sync_immich
    await _immich(request).put_metadata(asset_id, cfg.date_key, normalized)
    return normalized


@router.delete("/api/assets/{asset_id}/date")
async def api_delete_date(request: Request, asset_id: str):
    cfg = _state(request).cfg.sync_immich
    await _immich(request).delete_metadata(asset_id, cfg.date_key)
    return {"ok": True}


@router.post("/api/bulk/date")
async def api_bulk_date(request: Request, payload: dict = Body(...)):
    ids = payload.get("ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        raise HTTPException(422, "ids must be a non-empty list of asset ids")
    if len(ids) > 500:
        raise HTTPException(422, "at most 500 assets per bulk write")
    try:
        normalized = dates.validate(payload.get("date"))
    except dates.DateError as exc:
        raise HTTPException(422, str(exc))

    immich = _immich(request)
    cfg = _state(request).cfg.sync_immich
    semaphore = asyncio.Semaphore(6)

    async def one(asset_id: str) -> dict | None:
        async with semaphore:
            try:
                await immich.put_metadata(asset_id, cfg.date_key, normalized)
                return None
            except ImmichError as exc:
                return {"id": asset_id, "error": str(exc)}
            except Exception as exc:  # keep the bulk accounting intact no matter what
                log.exception("bulk date write failed for asset %s", asset_id)
                return {"id": asset_id, "error": f"internal error: {exc}"}

    failures = [f for f in await asyncio.gather(*(one(i) for i in ids)) if f]
    return {"ok": len(ids) - len(failures), "failed": failures, "date": normalized}


# -- scan-role editing ----------------------------------------------------------


@router.put("/api/assets/{asset_id}/scan")
async def api_put_scan(request: Request, asset_id: str, payload: dict = Body(...)):
    try:
        normalized = scan.validate(payload)
    except scan.ScanError as exc:
        raise HTTPException(422, str(exc))
    cfg = _state(request).cfg.sync_immich
    await _immich(request).put_metadata(asset_id, cfg.scan_key, normalized)
    return normalized


@router.delete("/api/assets/{asset_id}/scan")
async def api_delete_scan(request: Request, asset_id: str):
    cfg = _state(request).cfg.sync_immich
    await _immich(request).delete_metadata(asset_id, cfg.scan_key)
    return {"ok": True}


# -- Gramps title + sync ---------------------------------------------------------


@router.put("/api/assets/{asset_id}/gramps")
async def api_put_gramps(request: Request, asset_id: str, payload: dict = Body(...)):
    """Set the Gramps media-object title, merged into the gda.gramps KV entry."""
    title = str(payload.get("title") or "").strip()
    immich = _immich(request)
    cfg = _state(request).cfg.sync_immich
    current = (await immich.get_metadata(asset_id)).get(cfg.gramps_key) or {}
    current["schema"] = 1
    if title:
        current["title"] = title
    else:
        current.pop("title", None)
    if set(current) == {"schema"}:  # nothing left worth keeping
        await immich.delete_metadata(asset_id, cfg.gramps_key)
        return None
    await immich.put_metadata(asset_id, cfg.gramps_key, current)
    return current


# -- recto/verso pairing ---------------------------------------------------------


def validate_pair(recto_kv: dict, verso_kv: dict, cfg) -> str | None:
    """Reason the pair is not allowed, or None. A verso carries no metadata
    of its own, so an already-synced asset must not become one — its Gramps
    media object would be orphaned from all future updates."""
    if recto_kv.get(cfg.verso_key):
        return "the chosen recto is already paired — unlink it first"
    if verso_kv.get(cfg.verso_key):
        return "the chosen verso is already paired — unlink it first"
    if (verso_kv.get(cfg.gramps_key) or {}).get("gramps_id"):
        return "the chosen verso is already synced to Gramps as its own media object"
    return None


@router.put("/api/pair")
async def api_pair(request: Request, payload: dict = Body(...)):
    """Link two assets as front/back of one physical photo. The verso keeps
    no metadata of its own; browsing and sync treat the recto as the object."""
    recto = str(payload.get("recto") or "")
    verso = str(payload.get("verso") or "")
    if not valid_uuid(recto) or not valid_uuid(verso):
        raise HTTPException(422, "recto and verso must be asset ids")
    if recto == verso:
        raise HTTPException(422, "a photo cannot be its own verso")
    immich = _immich(request)
    cfg = _state(request).cfg.sync_immich
    recto_kv = await immich.get_metadata(recto)
    verso_kv = await immich.get_metadata(verso)
    reason = validate_pair(recto_kv, verso_kv, cfg)
    if reason:
        raise HTTPException(409, reason)
    await immich.put_metadata(recto, cfg.verso_key, {"schema": 1, "verso": verso})
    await immich.put_metadata(verso, cfg.verso_key, {"schema": 1, "recto": recto})
    return {"recto": recto, "verso": verso}


# -- stack membership -------------------------------------------------------------


def plan_stack(asset_ids: list[str], stack_of: dict, kv_of: dict, cfg) -> tuple[list[str], str]:
    """Order the ids for Immich's POST /stacks (first = primary) and pick the
    primary. Raises ValueError with a user-facing reason when the selection
    can't be stacked.

    - Selection touching ONE existing stack merges into it, keeping its
      primary; touching two is refused (unstack first).
    - A brand-new stack's primary is the first-selected photo.
    - Joining photos become hidden variants, so a joiner may be neither a
      verso nor already synced to Gramps as its own media object.
    """
    touched = {stack_of[a]["id"] for a in asset_ids if a in stack_of}
    if len(touched) > 1:
        raise ValueError("those photos span two existing stacks — remove from one first")
    if touched:
        member = next(a for a in asset_ids if a in stack_of)
        primary = stack_of[member]["primaryAssetId"]
    else:
        primary = asset_ids[0]
    if ((kv_of.get(primary) or {}).get(cfg.verso_key) or {}).get("recto"):
        raise ValueError("the main photo is the verso of another — unlink it first")
    for a in asset_ids:
        if a == primary or a in stack_of:  # existing members are already governed
            continue
        kv = kv_of.get(a) or {}
        if (kv.get(cfg.verso_key) or {}).get("recto"):
            raise ValueError("a selected photo is the verso of another — unlink it first")
        if (kv.get(cfg.gramps_key) or {}).get("gramps_id"):
            raise ValueError(
                "a selected photo is already synced to Gramps as its own media — "
                "it can't become a hidden variant")
    return [primary] + [a for a in asset_ids if a != primary], primary


@router.post("/api/stacks")
async def api_create_stack(request: Request, payload: dict = Body(...)):
    """Stack the selected photos — a brand-new stack, or a merge into the one
    existing stack the selection touches."""
    ids = payload.get("asset_ids")
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise HTTPException(422, "asset_ids must be a list of asset ids")
    ids = list(dict.fromkeys(ids))
    if len(ids) < 2:
        raise HTTPException(422, "select at least two photos to stack")
    bad = [i for i in ids if not valid_uuid(i)]
    if bad:
        raise HTTPException(422, f"invalid asset ids: {bad[:3]}")
    immich = _immich(request)
    cfg = _state(request).cfg.sync_immich
    stack_of: dict = {}
    for s in await immich.list_stacks():  # fresh, not the 60s cache — guards need truth
        for a in s.get("assets") or []:
            stack_of[a["id"]] = {"id": s["id"], "primaryAssetId": s.get("primaryAssetId")}
    kv_of = await immich.get_metadata_many(ids)
    if any(kv_of.get(i) is None for i in ids):
        raise HTTPException(502, "could not read metadata for every selected photo — try again")
    try:
        ordered, primary = plan_stack(ids, stack_of, kv_of, cfg)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    stack = await immich.create_stack(ordered)
    caches = _state(request).caches
    caches.pop("photos_stacks", None)
    caches.pop("photos_merge", None)
    return {"stack_id": stack.get("id"), "primary": stack.get("primaryAssetId")}


@router.delete("/api/stacks/assets/{asset_id}")
async def api_unstack(request: Request, asset_id: str):
    """Remove one variant from its stack (it becomes a loose photo again).
    The main can't leave — its metadata IS the stack's; pick a new main first."""
    if not valid_uuid(asset_id):
        raise HTTPException(422, "invalid asset id")
    immich = _immich(request)
    asset = await immich.get_asset(asset_id)
    stack = asset.get("stack") or {}
    if not stack.get("id"):
        raise HTTPException(404, "this photo is not in a stack")
    if stack.get("primaryAssetId") == asset_id:
        raise HTTPException(409, "this is the stack's main image — make another variant the main first")
    await immich.remove_stack_asset(stack["id"], asset_id)
    remaining = await immich.get_stack(stack["id"])
    if len(remaining.get("assets") or []) < 2:  # a one-photo stack is no stack
        await immich.delete_stack(stack["id"])
    caches = _state(request).caches
    caches.pop("photos_stacks", None)
    caches.pop("photos_merge", None)
    return {"ok": True}


# -- stack main image ------------------------------------------------------------


def plan_primary_move(old_kv: dict, cfg) -> tuple[dict, list[str]]:
    """What making a different variant the main moves with it: (writes onto
    the new primary, keys to delete from the old one).

    gda.date, gda.gramps and gda.verso describe the PHOTO, so they follow the
    main; gda.scan describes the individual FILE's role in the media-ID
    scheme (original / AI-edited / crop), so it stays on its asset. Per key,
    the old main's value wins; where it had none, the new main keeps its own
    (survivors of historically split metadata).
    """
    writes: dict = {}
    deletes: list[str] = []
    for key in (cfg.date_key, cfg.gramps_key, cfg.verso_key):
        value = old_kv.get(key)
        if value is not None:
            writes[key] = value
            deletes.append(key)
    return writes, deletes


@router.put("/api/stacks/{stack_id}/primary")
async def api_make_main(request: Request, stack_id: str, payload: dict = Body(...)):
    """Make one stack member the main image. The stack's gda metadata moves
    with the main (the next Sync scan repoints the Gramps media to the new
    main's file)."""
    asset_id = str(payload.get("asset_id") or "")
    if not valid_uuid(asset_id):
        raise HTTPException(422, "asset_id required")
    immich = _immich(request)
    cfg = _state(request).cfg.sync_immich
    stack = await immich.get_stack(stack_id)
    members = [a["id"] for a in stack.get("assets") or []]
    if asset_id not in members:
        raise HTTPException(422, "that asset is not a member of this stack")
    new_kv = await immich.get_metadata(asset_id)
    if (new_kv.get(cfg.verso_key) or {}).get("recto"):
        # A verso as the main would hide the whole stack (versos never
        # render) and, when its recto is the old primary, corrupt the pair
        # into a self-reference.
        raise HTTPException(409, "that variant is the verso of another photo — unlink it first")
    old_primary = stack.get("primaryAssetId")

    async def rewire_partner(link: dict) -> None:
        partner = link.get("verso") or link.get("recto")
        if partner and valid_uuid(partner) and partner != asset_id:
            pointer = "recto" if "verso" in link else "verso"
            await immich.put_metadata(partner, cfg.verso_key, {"schema": 1, pointer: asset_id})

    if old_primary != asset_id:
        # Genuine switch. Order matters for failure tolerance: switch the
        # primary first (the authoritative state), copy the old main's
        # metadata over (its values WIN — they were the maintained ones;
        # remnants on the new main were invisible), rewire the verso
        # partner, delete from the old main LAST — a mid-way failure leaves
        # duplicates on a hidden child, never loss. Re-running the endpoint
        # afterwards falls into the completion sweep below and finishes.
        old_kv = await immich.get_metadata(old_primary) if old_primary else {}
        writes, deletes = plan_primary_move(old_kv, cfg)
        await immich.update_stack_primary(stack_id, asset_id)
        for key, value in writes.items():
            await immich.put_metadata(asset_id, key, value)
        await rewire_partner(writes.get(cfg.verso_key) or {})
        for key in deletes:
            await immich.delete_metadata(old_primary, key)
    else:
        # Already the main: complete any interrupted move — copy movable
        # keys the main lacks from other members, rewire, then clear member
        # copies of keys the main now carries (stale duplicates).
        primary_kv = dict(new_kv)
        for member in members:
            if member == asset_id:
                continue
            member_kv = await immich.get_metadata(member)
            writes, _deletes = plan_primary_move(member_kv, cfg)
            for key, value in writes.items():
                if key not in primary_kv:
                    await immich.put_metadata(asset_id, key, value)
                    primary_kv[key] = value
                    if key == cfg.verso_key:
                        await rewire_partner(value)
            for key in writes:
                if key in primary_kv:
                    await immich.delete_metadata(member, key)
        # A partner whose back-pointer still names the old main (rewire was
        # the step that failed) gets repaired here.
        link = primary_kv.get(cfg.verso_key) or {}
        partner = link.get("verso") or link.get("recto")
        if partner and valid_uuid(partner) and partner != asset_id:
            pointer = "recto" if "verso" in link else "verso"
            partner_link = (await immich.get_metadata(partner)).get(cfg.verso_key) or {}
            if partner_link.get(pointer) != asset_id:
                await immich.put_metadata(partner, cfg.verso_key, {"schema": 1, pointer: asset_id})

    caches = _state(request).caches
    caches.pop("photos_stacks", None)
    caches.pop("photos_merge", None)
    return {"ok": True, "primary": asset_id}


@router.delete("/api/pair/{asset_id}")
async def api_unpair(request: Request, asset_id: str):
    """Unlink a recto/verso pair, given either side."""
    immich = _immich(request)
    cfg = _state(request).cfg.sync_immich
    link = (await immich.get_metadata(asset_id)).get(cfg.verso_key) or {}
    other = link.get("verso") or link.get("recto")
    if not other or not valid_uuid(other):
        raise HTTPException(404, "this asset is not paired")
    # The OTHER side first: if the second delete fails, the caller's own link
    # survives, so simply retrying Unlink still works (delete_metadata
    # tolerates the already-cleared side).
    await immich.delete_metadata(other, cfg.verso_key)
    await immich.delete_metadata(asset_id, cfg.verso_key)
    return {"ok": True}
