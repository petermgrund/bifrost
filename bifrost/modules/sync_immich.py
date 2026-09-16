"""Immich to Gramps media sync"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from datetime import datetime, timezone
from typing import AsyncIterator

from ..core import ids
from ..core.clients import GrampsClient, ImmichClient
from ..core.clients.immich import ImmichError
from ..core.config import SyncImmichConfig
from ..core.events import SyncEvent
from .citations import next_sequential_id
from .sync_paperless import build_note_obj, format_gramps_date

_MODIFIERS = {"regular": 0, "before": 1, "after": 2, "about": 3, "range": 4, "span": 5, "textonly": 6}
_QUALITIES = {"regular": 0, "estimated": 1, "calculated": 2}

TAG_SYNC_DATE = "sync/date"
TAG_SYNC_LOCATION = "sync/location"
TAG_SYNC_DESCRIPTION = "sync/description"
TAG_SYNC_MANUAL_FACES = "sync/manualfaces"
TAG_DATE_APPROXIMATE = "date/approximate"
TAG_DATE_BEFORE = "date/before"
TAG_DATE_AFTER = "date/after"
TAG_DATE_ESTIMATED = "date/estimated"
TAG_DATE_CALCULATED = "date/calculated"
TAG_DATE_YEAR = "date/year"
TAG_DATE_MONTH = "date/month"
METADATA_KEY = "bifrost"
NOTE_TYPE = "Media Note"
_URL_LINE_RE = re.compile(r"^https?://\S+$")

EARTH_RADIUS_KM = 6371.0
MAX_PLACE_DISTANCE_KM = 0.25


def tag_values(asset: dict) -> set[str]:
    return {t["value"].lower() for t in asset.get("tags") or [] if t.get("value")}


_TAG_CONFLICT_GROUPS = (
    {TAG_DATE_APPROXIMATE, TAG_DATE_BEFORE, TAG_DATE_AFTER},
    {TAG_DATE_ESTIMATED, TAG_DATE_CALCULATED},
    {TAG_DATE_YEAR, TAG_DATE_MONTH},
)


def merge_tag_values(owner_tags: set[str], other_tags: set[str]) -> set[str]:
    """owner wins inside each date group"""
    merged = set(owner_tags)
    for tag in other_tags:
        group = next((g for g in _TAG_CONFLICT_GROUPS if tag in g), None)
        if group and owner_tags & group:
            continue
        merged.add(tag)
    return merged


def build_gramps_date(asset: dict) -> dict | None:
    exif = asset.get("exifInfo") or {}
    # wall clock never the UTC dateTimeOriginal
    dt_str = asset.get("localDateTime") or exif.get("dateTimeOriginal")
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
    except ValueError:
        return None

    tags = tag_values(asset)
    if TAG_DATE_APPROXIMATE in tags:
        modifier = _MODIFIERS["about"]
    elif TAG_DATE_BEFORE in tags:
        modifier = _MODIFIERS["before"]
    elif TAG_DATE_AFTER in tags:
        modifier = _MODIFIERS["after"]
    else:
        modifier = _MODIFIERS["regular"]

    if TAG_DATE_CALCULATED in tags:
        quality = _QUALITIES["calculated"]
    elif TAG_DATE_ESTIMATED in tags:
        quality = _QUALITIES["estimated"]
    else:
        quality = _QUALITIES["regular"]

    if TAG_DATE_YEAR in tags:
        day, month = 0, 0
    elif TAG_DATE_MONTH in tags:
        day, month = 0, dt.month
    elif modifier == _MODIFIERS["about"]:
        day, month = 0, dt.month
    else:
        day, month = dt.day, dt.month

    return {"_class": "Date", "dateval": [day, month, dt.year, False],
            "modifier": modifier, "quality": quality, "text": ""}


def asset_coords(asset: dict) -> tuple[float, float] | None:
    exif = asset.get("exifInfo") or {}
    lat, lon = exif.get("latitude"), exif.get("longitude")
    if lat is None or lon is None:
        return None
    return (round(lat, 4), round(lon, 4))


def parse_gramps_coord(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    sign = 1
    if value[0] in "SsWw":
        sign = -1
        value = value[1:]
    elif value[0] in "NnEe":
        value = value[1:]
    try:
        return sign * float(value)
    except (ValueError, TypeError):
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = (math.radians(v) for v in (lat1, lon1, lat2, lon2))
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def closest_place(lat: float, lon: float, places: list[dict]) -> tuple[dict, float] | None:
    best, best_dist = None, float("inf")
    for place in places:
        p_lat = parse_gramps_coord(place.get("lat", ""))
        p_lon = parse_gramps_coord(place.get("long", ""))
        if p_lat is None or p_lon is None:
            continue
        dist = haversine_km(lat, lon, round(p_lat, 4), round(p_lon, 4))
        if dist < best_dist:
            best, best_dist = place, dist
    if best is None or best_dist > MAX_PLACE_DISTANCE_KM:
        return None
    return (best, best_dist)


async def linkable_places(gramps: GrampsClient, cfg: SyncImmichConfig) -> list[dict]:
    if not cfg.place_tag_handle:
        return []
    return [
        p for p in await gramps.list_places_full()
        if cfg.place_tag_handle in (p.get("tag_list") or [])
        and p.get("lat") and p.get("long")
    ]


class SyncError(Exception):
    """Sync failure carrying the HTTP status the route should surface"""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def translate_path(original_path: str, mappings: tuple[tuple[str, str], ...]) -> str:
    for immich_prefix, gramps_prefix in mappings:
        if original_path.startswith(immich_prefix):
            return gramps_prefix + original_path[len(immich_prefix):]
    raise SyncError(
        400,
        f"originalPath {original_path!r} is under no configured path mapping, "
        "add it to sync.immich.path_mappings and mount it in grampsweb config first",
    )


WEB_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"})


def wants_preview(asset: dict, cfg: SyncImmichConfig) -> bool:
    """Whether Gramps gets Immich's preview instead of the original"""
    mime = asset.get("originalMimeType") or ""
    return bool(cfg.previews_prefix) and mime.startswith("image/") and mime not in WEB_IMAGE_MIMES


def gramps_file(asset: dict, cfg: SyncImmichConfig,
                preview: tuple[str, str] | None = None) -> tuple[str, str]:
    """(path, mime) Gramps should reference for the asset"""
    if not wants_preview(asset, cfg):
        return (translate_path(asset["originalPath"], cfg.path_mappings),
                asset.get("originalMimeType") or "image/jpeg")
    aid = asset["id"]
    if preview is None:
        raise SyncError(502, f"Immich has no preview of {asset.get('originalFileName') or aid} yet")
    owner = asset.get("ownerId") or ""
    if not owner:
        raise SyncError(502, f"Immich returned no ownerId for {aid}")
    ext, mime = preview
    return f"{cfg.previews_prefix}{owner}/{aid[:2]}/{aid[2:4]}/{aid}_preview.{ext}", mime


async def preview_of(accounts: list[ImmichClient], asset: dict,
                     cfg: SyncImmichConfig) -> tuple[str, str] | None:
    """The preview rendition Immich serves for an asset that needs one"""
    if not wants_preview(asset, cfg):
        return None
    client, _err = await owner_client(accounts, asset)
    try:
        return await client.preview_file(asset["id"])
    except ImmichError as exc:
        raise SyncError(502, f"preview lookup failed: {exc.message}")


def person_links_map(conn: sqlite3.Connection) -> dict[str, dict]:
    """{immich_person_id: {handle, label}} from the person_links register"""
    rows = conn.execute(
        "SELECT immich_person_id, gramps_handle, label FROM person_links"
    ).fetchall()
    return {r["immich_person_id"]: {"handle": r["gramps_handle"],
                                    "label": r["label"] or ""}
            for r in rows}


async def _user_id(client: ImmichClient) -> str:
    uid = getattr(client, "_me_id", "")
    if not uid:
        uid = (await client.get_me()).get("id") or ""
        client._me_id = uid
    return uid


_OWNER_TAGS_KEY = "bifrostOwnerTags"


def _merge_copies(copies: list[tuple[str, dict]]) -> dict:
    """One canonical asset from per-account (user_id, detail) copies:
    the owner account's copy with the union of every account's tags.
    When no copy is provably the owner's, no preference: plain union.
    The owner's OWN tags ride along under _OWNER_TAGS_KEY (None when the
    owner is unknown) because tag namespaces are per user."""
    owner = copies[0][1].get("ownerId")
    matched = next(((uid, c) for uid, c in copies if uid == owner), None)
    base = matched[1] if matched else copies[0][1]
    owner_tags = tag_values(base) if matched else set()
    other_tags = set().union(*(tag_values(c) for _, c in copies)) - owner_tags
    tags = merge_tag_values(owner_tags, other_tags)
    spelling = {(t.get("value") or "").lower(): t["value"]
                for _, c in copies for t in c.get("tags") or [] if t.get("value")}
    return {**base,
            "tags": [{"value": spelling.get(t, t)} for t in sorted(tags)],
            _OWNER_TAGS_KEY: sorted(owner_tags) if matched else None}


def owner_tag_values(asset: dict) -> set[str] | None:
    """The owning account's own tags: a tag seen only through another
    account does not count. None means the owner could not be proven,
    so callers must not guess. With one account, what that key sees IS
    its own namespace."""
    if _OWNER_TAGS_KEY in asset:
        stored = asset[_OWNER_TAGS_KEY]
        return None if stored is None else set(stored)
    return tag_values(asset)


async def _merged_details(
    accounts: list[ImmichClient], asset_ids: list[str],
) -> dict[str, dict | None]:
    """Detail per id across accounts; None marks an id no account could read"""
    if len(accounts) == 1:
        return await accounts[0].get_assets_many(asset_ids)
    uids = []
    for c in accounts:
        try:
            uids.append(await _user_id(c))
        except ImmichError:
            # owner preference degrades; owner_client surfaces the failure
            uids.append("")
    per_account = [await c.get_assets_many(asset_ids) for c in accounts]
    merged: dict[str, dict | None] = {}
    for aid in asset_ids:
        copies = [(uid, d.get(aid)) for uid, d in zip(uids, per_account)
                  if d.get(aid) is not None]
        merged[aid] = _merge_copies(copies) if copies else None
    return merged


async def _merged_one(accounts: list[ImmichClient], asset_id: str) -> dict:
    """Single-asset detail across accounts. A 404 is only trustworthy when
    EVERY account 404'd; any harder failure maps to 502."""
    errors: list[ImmichError] = []
    copies: list[tuple[str, dict]] = []
    for client in accounts:
        try:
            detail = await client.get_asset(asset_id)
        except ImmichError as exc:
            errors.append(exc)
            continue
        try:
            uid = "" if len(accounts) == 1 else await _user_id(client)
        except ImmichError:
            uid = ""
        copies.append((uid, detail))
    if not copies:
        if not errors or all(e.status in (400, 404) for e in errors):
            exc = errors[0] if errors else ImmichError(404, "asset not found")
            raise SyncError(404, f"asset lookup failed: {exc.message}")
        hard = next(e for e in errors if e.status not in (400, 404))
        raise SyncError(502, f"asset lookup failed: {hard.message}")
    if len(copies) == 1:
        return copies[0][1]
    return _merge_copies(copies)


def _attr(attr_type: str, value: str) -> dict:
    return {
        "_class": "Attribute",
        "type": attr_type,
        "value": value,
        "private": False,
        "citation_list": [],
        "note_list": [],
    }


_FACE_PAD = 0.15


def _face_rect(face: dict, pad: bool = True) -> list:
    """Immich's pixel face box as a Gramps percent rect"""
    w, h = face.get("imageWidth") or 0, face.get("imageHeight") or 0
    coords = [face.get("boundingBoxX1"), face.get("boundingBoxY1"),
              face.get("boundingBoxX2"), face.get("boundingBoxY2")]
    if not w or not h or any(c is None for c in coords):
        return []
    x1, y1, x2, y2 = coords
    if x2 <= x1 or y2 <= y1:
        return []
    if pad:
        bw, bh = (x2 - x1) * _FACE_PAD, (y2 - y1) * _FACE_PAD
        x1, x2, y1, y2 = x1 - bw, x2 + bw, y1 - bh, y2 + bh
    rect = [round(x1 / w * 100), round(y1 / h * 100),
            round(x2 / w * 100), round(y2 / h * 100)]
    return [min(100, max(0, v)) for v in rect]


def _media_ref(media_handle: str, rect: list | None = None) -> dict:
    return {
        "_class": "MediaRef",
        "ref": media_handle,
        "rect": rect or [],
        "attribute_list": [],
        "citation_list": [],
        "note_list": [],
        "private": False,
    }


def new_face_results() -> dict:
    return {"people_linked": [], "people_unmatched": [], "people_failed": []}


async def owner_client(
    accounts: list[ImmichClient], asset: dict,
) -> tuple[ImmichClient, str | None]:
    """The owning account's client. Tags and faces are both per user:
    cross-account face reads come back person-stripped, and a tag written
    through the wrong key lands in the wrong namespace. A failed identity
    probe never ends the search: the owner may still match."""
    owner = asset.get("ownerId")
    error: str | None = None
    if owner and len(accounts) > 1:
        for client in accounts:
            try:
                if owner == await _user_id(client):
                    return client, None
            except ImmichError as exc:
                label = getattr(client, "label", "") or "account"
                error = error or f"{label} identity lookup failed: {exc.message}"
    return accounts[0], error


async def link_asset_faces(
    gramps: GrampsClient,
    faces_client: ImmichClient,
    asset: dict,
    asset_id: str,
    media_handle: str,
    gid: str | None,
    person_map: dict[str, dict],
    results: dict,
    apply: bool = True,
) -> AsyncIterator[SyncEvent]:
    """Add missing person↔media face refs for one asset. Accumulates into
    `results` (a new_face_results dict); never overwrites a hand-set rect.
    apply=False previews: same events, no Gramps writes."""
    try:
        faces = await faces_client.get_faces(asset_id)
    except ImmichError as exc:
        faces = []
        yield SyncEvent(
            kind="item", entity="face", action="failed", source_id=asset_id,
            detail=f"face lookup failed: {exc.message}",
        )

    pad = TAG_SYNC_MANUAL_FACES not in tag_values(asset)
    linked_people: dict[str, tuple[str, list]] = {}
    for face in faces:
        person = face.get("person") or {}
        pid = person.get("id")
        if not pid:
            continue
        entry = person_map.get(pid)
        if entry:
            label = entry["label"] or person.get("name") or pid
            prev = linked_people.get(entry["handle"])
            if prev is None or not prev[1]:
                linked_people[entry["handle"]] = (label, _face_rect(face, pad=pad))
        else:
            name = person.get("name") or pid
            if name not in results["people_unmatched"]:
                results["people_unmatched"].append(name)

    for handle, (label, rect) in linked_people.items():
        try:
            person = await gramps.get_person(handle)
            refs = person.setdefault("media_list", [])
            existing = [r for r in refs if r.get("ref") == media_handle]
            if existing:
                # never overwrite a hand-set rect
                if rect and not any(r.get("rect") for r in existing):
                    if apply:
                        existing[0]["rect"] = rect
                        await gramps.update_person(handle, person)
                    yield SyncEvent(
                        kind="item", entity="face", action="updated",
                        source_id=asset_id, gramps_id=gid, title=label,
                        detail="face box added",
                    )
                results["people_linked"].append(label)
                continue
            if apply:
                refs.append(_media_ref(media_handle, rect))
                await gramps.update_person(handle, person)
            results["people_linked"].append(label)
            yield SyncEvent(
                kind="item", entity="face", action="created", source_id=asset_id,
                gramps_id=gid, title=label, detail="person↔media association",
            )
        except Exception as exc:
            results["people_failed"].append({"person": label, "error": str(exc)[:200]})
            yield SyncEvent(
                kind="item", entity="face", action="failed", source_id=asset_id,
                gramps_id=gid, title=label, detail=str(exc)[:200],
            )


async def sync_one_asset(
    gramps: GrampsClient,
    accounts: list[ImmichClient],
    conn: sqlite3.Connection,
    cfg: SyncImmichConfig,
    asset_id: str,
    gramps_id: str | None = None,
    update: bool = False,
    places: dict | None = None,
) -> AsyncIterator[SyncEvent]:
    """Create the Gramps media for one Immich asset; re-runs finish links idempotently"""
    yield SyncEvent(kind="started", detail=f"immich asset {asset_id}")

    asset = await _merged_one(accounts, asset_id)
    if asset.get("isTrashed"):
        raise SyncError(400, "asset is in the Immich trash")
    stack = asset.get("stack") or {}
    if stack.get("primaryAssetId") and stack["primaryAssetId"] != asset_id:
        raise SyncError(400, "this asset is a stack variant. sync the stack's main image instead")

    date_obj, date_display = wanted_date(asset)

    row = conn.execute(
        "SELECT gramps_id FROM minted_media WHERE source_system='immich' AND source_id=?",
        (asset_id,),
    ).fetchone()
    if row is None and stack.get("primaryAssetId"):
        #  register may ride on a hidden variant
        try:
            stacks = [s for client in accounts for s in await client.list_stacks()]
        except ImmichError as exc:
            raise SyncError(502, f"could not list Immich stacks: {exc.message}")
        member_ids: list[str] = []
        for s in stacks:
            aids = [a["id"] for a in (s.get("assets") or [])]
            if asset_id in aids:
                member_ids = aids
                break
        if member_ids:
            rows = conn.execute(
                "SELECT gramps_id FROM minted_media WHERE source_system='immich' "
                f"AND source_id IN ({','.join('?' * len(member_ids))})",
                member_ids,
            ).fetchall()
            if len(rows) > 1:
                raise SyncError(
                    400,
                    "two synced media resolve to the same stack main, "
                    "unstack them or fix the register before syncing",
                )
            row = rows[0] if rows else None
    existing = await gramps.get_media_by_gramps_id(row[0]) if row else None

    counts = new_counts()
    updated_cols: dict = {}
    refreshed = existing is not None and update
    if existing is not None:
        gid = existing["gramps_id"]
        media_handle = existing["handle"]
        title = existing.get("desc") or ""
        gramps_path = existing.get("path") or ""
        media_obj = existing
        created = False
        yield SyncEvent(
            kind="item", entity="media", action="skipped", source_id=asset_id,
            gramps_id=gid, title=title, detail="already in Gramps",
        )
        if update:
            async for ev in update_synced(gramps, accounts, conn, cfg, gid, asset, existing,
                                          places, True, None, counts):
                if ev.kind == "item" and ev.entity == "media" and ev.action == "updated":
                    updated_cols.update((ev.data or {}).get("cols") or {})
                yield ev
            title = existing.get("desc") or title
            gramps_path = existing.get("path") or gramps_path
    else:
        live_ids = await gramps.list_media_gramps_ids()
        if gramps_id:
            gid = gramps_id.strip().upper()
            if not ids.MANUAL_ID_RE.match(gid):
                raise SyncError(400, f"invalid gramps_id {gramps_id!r} (6 chars, safe alphabet)")
            if gid in live_ids:
                raise SyncError(400, f"gramps_id {gid} already exists in Gramps")
        else:
            gid = ids.generate_gramps_id(live_ids | ids.unminted_reserved(conn))

        gramps_path, mime = gramps_file(asset, cfg, await preview_of(accounts, asset, cfg))
        title = wanted_title(asset) or gid
        media_handle = ids.generate_handle()

        media_obj = {
            "_class": "Media",
            "handle": media_handle,
            "gramps_id": gid,
            "desc": title,
            "path": gramps_path,
            "mime": mime,
            "private": False,
            "change": int(datetime.now(timezone.utc).timestamp()),
            "attribute_list": [_attr("Immich ID", asset_id)]
            + ([_attr("Immich URL", f"{cfg.public_url}/photos/{asset_id}")] if cfg.public_url else []),
        }
        if date_obj:
            media_obj["date"] = date_obj

        try:
            await gramps.create_media(media_obj)
        except Exception as exc:
            raise SyncError(502, f"Gramps create failed: {exc}")
        with conn:
            ids.mark_minted(conn, gid, _now())
            conn.execute(
                "INSERT OR REPLACE INTO minted_media "
                "(gramps_id, source_system, source_id, title, minted_at) VALUES (?, 'immich', ?, ?, ?)",
                (gid, asset_id, title, _now()),
            )
        created = True
        yield SyncEvent(
            kind="item", entity="media", action="created", source_id=asset_id,
            gramps_id=gid, title=title, detail=gramps_path,
        )

    if not refreshed:
        tag_cols = id_tag_plan(asset, gid, cfg)
        if tag_cols:
            tag_error = await write_id_tag(accounts, asset, gid, cfg)
            if tag_error:
                yield SyncEvent(
                    kind="item", entity="tag", action="failed", source_id=asset_id,
                    gramps_id=gid, title=title, detail=tag_error)
            else:
                yield SyncEvent(
                    kind="item", entity="tag", action="created", source_id=asset_id,
                    gramps_id=gid, title=title, detail=id_tag_path(cfg, gid))
        if created or tag_cols:
            record_error = await write_link_record(accounts, conn, asset, gid, cfg)
            if record_error:
                yield SyncEvent(
                    kind="item", entity="tag", action="failed", source_id=asset_id,
                    gramps_id=gid, title=title, detail=record_error)

    person_map = person_links_map(conn)
    face_results = new_face_results()
    faces_client, account_err = await owner_client(accounts, asset)
    if account_err:
        yield SyncEvent(
            kind="item", entity="face", action="failed", source_id=asset_id,
            detail=account_err,
        )
    async for ev in link_asset_faces(
            gramps, faces_client, asset, asset_id, media_handle, gid,
            person_map, face_results):
        yield ev
    people_linked = face_results["people_linked"]
    people_unmatched = face_results["people_unmatched"]
    people_failed = face_results["people_failed"]

    place_linked = None
    if not refreshed:
        try:
            found = await resolve_place(gramps, asset, cfg, places)
        except SyncError as exc:
            found = None
            yield SyncEvent(kind="item", entity="place", action="failed",
                            source_id=asset_id, detail=exc.detail)
        except Exception as exc:
            found = None
            yield SyncEvent(kind="item", entity="place", action="failed",
                            source_id=asset_id,
                            detail=f"could not list Gramps places: {str(exc)[:180]}")
        if found:
            place, how = found
            place_name = place_label(place)
            try:
                linked = await _link_place(gramps, place, media_handle)
                place_linked = place_name
                if linked:
                    yield SyncEvent(kind="item", entity="place", action="created",
                                    source_id=asset_id, gramps_id=place.get("gramps_id"),
                                    title=place_name, detail=_PLACE_DETAIL[how])
            except Exception as exc:
                yield SyncEvent(kind="item", entity="place", action="failed",
                                source_id=asset_id, title=place_name,
                                detail=str(exc)[:200])

    note_synced = None
    if not refreshed and cfg.note_sync_tag.lower() in tag_values(asset):
        try:
            ev = await sync_note(gramps, conn, asset_id, gid, media_obj, apply=True)
        except Exception as exc:
            yield SyncEvent(kind="item", entity="note", action="failed", source_id=asset_id,
                            gramps_id=gid, title=title, detail=str(exc)[:200])
        else:
            if ev:
                note_synced = ev.action
                yield ev

    yield SyncEvent(
        kind="summary", entity="media", gramps_id=gid, title=title,
        detail="created" if created else "already synced",
        data={
            "gramps_id": gid,
            "created": created,
            "title": title,
            "path": gramps_path,
            "date": date_display or None,
            "place_linked": place_linked,
            "people_linked": people_linked,
            "people_unmatched": people_unmatched,
            "people_failed": people_failed,
            "updated": updated_cols,
            "note": note_synced,
            "errors": counts["errors"],
        },
    )


_TAG_ASSET_CAP = 5000
_DETAIL_BATCH = 40
_PLACE_DETAIL = {"gps": "media↔place link (GPS)", "tag": "media↔place link"}


def new_counts() -> dict:
    return {"created": 0, "titles_updated": 0, "dates_updated": 0,
            "versions_updated": 0, "links_updated": 0, "places_linked": 0,
            "id_tags_written": 0, "notes_synced": 0, "skipped": 0, "errors": 0}


def split_description(text: str) -> tuple[str, str | None]:
    """(title, trailing URL line or None)"""
    lines = [line.strip() for line in (text or "").strip().splitlines()]
    if len(lines) >= 2 and _URL_LINE_RE.match(lines[-1]):
        return "\n".join(lines[:-1]).strip(), lines[-1]
    return "\n".join(lines).strip(), None


def wanted_title(asset: dict) -> str:
    if TAG_SYNC_DESCRIPTION in tag_values(asset):
        desc = split_description((asset.get("exifInfo") or {}).get("description") or "")[0]
        if desc:
            return desc
    return asset.get("originalFileName") or ""


def wanted_update_title(asset: dict) -> str | None:
    """None = hands off"""
    if TAG_SYNC_DESCRIPTION in tag_values(asset):
        return split_description((asset.get("exifInfo") or {}).get("description") or "")[0] or None
    return None


def wanted_date(asset: dict) -> tuple[dict | None, str]:
    if TAG_SYNC_DATE in tag_values(asset):
        d = build_gramps_date(asset)
        if d:
            return d, format_gramps_date(d)
    return None, ""


def dates_equal(gramps_date: dict | None, new_date: dict | None) -> bool:
    """Only the fields bifrost writes"""
    a, b = gramps_date or {}, new_date or {}
    return (
        (a.get("dateval") or []) == (b.get("dateval") or [])
        and (a.get("modifier") or 0) == (b.get("modifier") or 0)
        and (a.get("quality") or 0) == (b.get("quality") or 0)
        and (a.get("text") or "") == (b.get("text") or "")
    )


def id_tag_path(cfg: SyncImmichConfig, gramps_id: str) -> str:
    return f"{cfg.id_tag_prefix}/{gramps_id}"


def id_tag_plan(asset: dict, gramps_id: str | None, cfg: SyncImmichConfig) -> dict:
    """Pending-change col for the ID/{gramps_id} write-back ({} = in sync).
    Measured against the OWNER's namespace, never the merged tag view."""
    if not cfg.id_tag_prefix or not gramps_id:
        return {}
    own = owner_tag_values(asset)
    if own is None:
        return {}
    wanted = id_tag_path(cfg, gramps_id)
    prefix = f"{cfg.id_tag_prefix.lower()}/"
    stale = [t for t in own if t.startswith(prefix) and t != wanted.lower()]
    if wanted.lower() in own and not stale:
        return {}
    if stale:
        return {"id tag": f"{wanted} (replaces {len(stale)})"}
    return {"id tag": wanted}


async def write_id_tag(
    accounts: list[ImmichClient], asset: dict, gramps_id: str,
    cfg: SyncImmichConfig,
) -> str | None:
    """Put ID/{gramps_id} on the asset in the owning account's namespace and
    drop any other ID/* tag it carries. Returns an error string, else None.
    Best effort: a failure never rolls back the media that was created."""
    if not id_tag_plan(asset, gramps_id, cfg):
        return None
    client, _probe_error = await owner_client(accounts, asset)
    asset_id = asset["id"]
    wanted = id_tag_path(cfg, gramps_id)
    prefix = f"{cfg.id_tag_prefix.lower()}/"
    try:
        tag = await client.upsert_tag(wanted)
        await client.tag_asset(tag["id"], asset_id)
        for stale in sorted(t for t in (owner_tag_values(asset) or set())
                            if t.startswith(prefix) and t != wanted.lower()):
            found = await client.find_tag(stale)
            if found:
                await client.untag_asset(found["id"], asset_id)
    except ImmichError as exc:
        return f"ID tag write failed: {exc.message}"
    return None


def link_record(gramps_id: str | None, cfg: SyncImmichConfig, notes: str = "") -> dict:
    """The bifrost metadata record an asset carries in Immich"""
    rec: dict = {}
    if gramps_id:
        rec["gramps_id"] = gramps_id
        if cfg.gramps_public_url:
            rec["gramps_url"] = f"{cfg.gramps_public_url}/media/{gramps_id}"
    if (notes or "").strip():
        rec["notes"] = notes.strip()
    return rec


async def write_link_record(
    accounts: list[ImmichClient], conn: sqlite3.Connection, asset: dict,
    gramps_id: str, cfg: SyncImmichConfig,
) -> str | None:
    client, _probe_error = await owner_client(accounts, asset)
    row = note_for(conn, asset["id"], gramps_id)
    try:
        await client.upsert_asset_metadata(
            asset["id"], METADATA_KEY, link_record(gramps_id, cfg, row["text"] if row else ""))
    except ImmichError as exc:
        return f"link record write failed: {exc.message}"
    return None


def note_for(conn: sqlite3.Connection, asset_id: str, gramps_id: str | None) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM photo_notes WHERE asset_id=? OR (gramps_id IS NOT NULL AND gramps_id=?) "
        "ORDER BY asset_id=? DESC LIMIT 1",
        (asset_id, gramps_id or "", asset_id)).fetchone()


async def sync_note(
    gramps: GrampsClient, conn: sqlite3.Connection, asset_id: str, gramps_id: str,
    media: dict, apply: bool = True,
) -> SyncEvent | None:
    """Mirror the photo's note into a Gramps note on its media object"""
    row = note_for(conn, asset_id, gramps_id)
    text = (row["text"] if row else "").strip()
    if not text:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if row["note_handle"] and row["synced_hash"] == digest:
        return None
    is_update = bool(row["note_handle"])
    word = "updated" if is_update else "created"
    if not apply:
        return SyncEvent(kind="item", entity="note", action="would_update", source_id=asset_id,
                         gramps_id=gramps_id, title=media.get("desc"),
                         data={"cols": {"note": f"{len(text)} chars"}})
    if is_update:
        handle, nid = row["note_handle"], row["note_gramps_id"]
        await gramps.update_note(handle, build_note_obj(handle, nid, text, NOTE_TYPE))
    else:
        handle = ids.generate_handle()
        items = await gramps._paged("/notes/", keys="gramps_id")
        nid = next_sequential_id("N", {i["gramps_id"] for i in items if i.get("gramps_id")})
        await gramps.create_note(build_note_obj(handle, nid, text, NOTE_TYPE))
        notes = media.setdefault("note_list", [])
        if handle not in notes:
            notes.append(handle)
            await gramps.update_media(media["handle"], media)
    with conn:
        conn.execute(
            "UPDATE photo_notes SET gramps_id=?, note_handle=?, note_gramps_id=?, "
            "synced_hash=?, updated_at=? WHERE asset_id=?",
            (gramps_id, handle, nid, digest, _now(), row["asset_id"]))
    return SyncEvent(kind="item", entity="note", action=word, source_id=asset_id,
                     gramps_id=gramps_id, title=media.get("desc"),
                     data={"cols": {"note": f"{len(text)} chars"}})


def place_tag_value(asset: dict, cfg: SyncImmichConfig) -> str | None:
    """The Gramps place id named by the asset's Place/{id} tag"""
    if not cfg.place_tag_prefix:
        return None
    prefix = cfg.place_tag_prefix.lower() + "/"
    for tag in sorted((t.get("value") or "") for t in asset.get("tags") or []):
        if tag.lower().startswith(prefix) and len(tag) > len(prefix):
            return tag[len(prefix):]
    return None


def place_label(place: dict) -> str:
    return (place.get("name") or {}).get("value") or place.get("gramps_id") or "?"


def place_index(places: list[dict], cfg: SyncImmichConfig, failed: bool = False) -> dict:
    """Places by gramps_id plus the coordinate-bearing subset the GPS match uses"""
    return {
        "by_gid": {p["gramps_id"]: p for p in places if p.get("gramps_id")},
        "with_coords": [p for p in places
                        if cfg.place_tag_handle and cfg.place_tag_handle in (p.get("tag_list") or [])
                        and p.get("lat") and p.get("long")],
        "failed": failed,
    }


async def resolve_place(
    gramps: GrampsClient, asset: dict, cfg: SyncImmichConfig, index: dict | None,
) -> tuple[dict, str] | None:
    """(place, 'tag' | 'gps') for an asset, its Place tag first"""
    if index is not None and index.get("failed"):
        return None
    gid = place_tag_value(asset, cfg)
    if gid:
        if index is not None:
            place = index["by_gid"].get(gid)
        else:
            place = await gramps.get_place_by_gramps_id(gid)
        if place is None:
            raise SyncError(400, f"{cfg.place_tag_prefix}/{gid} names no Gramps place")
        return place, "tag"
    if TAG_SYNC_LOCATION not in tag_values(asset):
        return None
    coords = asset_coords(asset)
    if not coords:
        return None
    places = index["with_coords"] if index is not None else await linkable_places(gramps, cfg)
    result = closest_place(coords[0], coords[1], places)
    return (result[0], "gps") if result else None


async def _link_place(gramps: GrampsClient, place: dict, media_handle: str) -> bool:
    """Add the media to the place's gallery; False when it already was there"""
    refs = place.setdefault("media_list", [])
    if any(r.get("ref") == media_handle for r in refs):
        return False
    refs.append(_media_ref(media_handle))
    try:
        await gramps.update_place(place["handle"], place)
    except Exception:
        refs.pop()
        raise
    return True


def update_plan(asset: dict, media: dict, cfg: SyncImmichConfig,
                preview: tuple[str, str] | None = None) -> dict:
    """Pending-change cols for an already-synced asset ({} = in sync)"""
    cols: dict = {}
    title = wanted_update_title(asset)
    if title and title != (media.get("desc") or ""):
        cols["title"] = f"{media.get('desc')!r} → {title!r}"
    new_date, display = wanted_date(asset)
    if new_date and not dates_equal(media.get("date"), new_date):
        cols["date"] = f"{format_gramps_date(media.get('date'))} → {display}"
    if asset.get("originalPath"):
        gramps_path, _mime = gramps_file(asset, cfg, preview)
        if gramps_path != (media.get("path") or ""):
            cols["file"] = f"{media.get('path') or '(none)'} → {gramps_path}"
    aid = asset.get("id") or ""
    linked = next((a.get("value") for a in media.get("attribute_list") or []
                   if a.get("type") == "Immich ID"), None)
    if aid and linked != aid:
        cols["link"] = f"{linked or '(none)'} → {aid}"
    return cols


def _set_attr(media: dict, attr_type: str, value: str) -> None:
    for att in media.setdefault("attribute_list", []):
        if att.get("type") == attr_type:
            att["value"] = value
            return
    media["attribute_list"].append(_attr(attr_type, value))


async def _tagged_scope(immich: ImmichClient, tag_id: str) -> tuple[list[dict], bool]:
    items: list[dict] = []
    page: int | None = 1
    while page and len(items) < _TAG_ASSET_CAP:
        r = await immich.search_assets(page=page, size=200, tag_id=tag_id)
        items.extend(r["items"])
        page = r["nextPage"]
    return items, bool(page)


async def update_synced(
    gramps: GrampsClient,
    accounts: list[ImmichClient],
    conn: sqlite3.Connection,
    cfg: SyncImmichConfig,
    gid: str,
    asset: dict,
    media: dict | None,
    places: dict | None,
    apply: bool,
    selected: set[str] | None,
    counts: dict,
) -> AsyncIterator[SyncEvent]:
    """Bring one registered media object up to date with its Immich asset"""
    asset_id = asset["id"]
    if media is None:
        try:
            media = await gramps.get_media_by_gramps_id(gid)
        except Exception as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, gramps_id=gid,
                            title=wanted_title(asset),
                            detail=f"Gramps lookup failed: {str(exc)[:200]}")
            return
        if media is None:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, gramps_id=gid,
                            title=wanted_title(asset),
                            detail=f"the register points at {gid}, which is not in Gramps")
            return
    if apply:
        with conn:
            conn.execute(
                "UPDATE minted_media SET source_id=? WHERE gramps_id=? AND source_system='immich' "
                "AND source_id<>?", (asset_id, gid, asset_id))

    try:
        found = await resolve_place(gramps, asset, cfg, places)
    except SyncError as exc:
        found = None
        counts["errors"] += 1
        yield SyncEvent(kind="item", entity="place", action="failed",
                        source_id=asset_id, gramps_id=gid, detail=exc.detail)
    except Exception as exc:
        found = None
        counts["errors"] += 1
        yield SyncEvent(kind="item", entity="place", action="failed",
                        source_id=asset_id, gramps_id=gid,
                        detail=f"could not list Gramps places: {str(exc)[:180]}")
    if found:
        place, _how = found
        refs = place.setdefault("media_list", [])
        if not any(r.get("ref") == media["handle"] for r in refs):
            place_name = place_label(place)
            if not apply:
                yield SyncEvent(kind="item", entity="place", action="would_update",
                                source_id=asset_id, gramps_id=place.get("gramps_id"),
                                title=place_name, data={"cols": {"place": place_name}})
            # place-only rows select as "place:<id>"
            elif selected is None or {f"media:{asset_id}", f"place:{asset_id}"} & selected:
                try:
                    await _link_place(gramps, place, media["handle"])
                    counts["places_linked"] += 1
                    yield SyncEvent(kind="item", entity="place", action="updated",
                                    source_id=asset_id, gramps_id=place.get("gramps_id"),
                                    title=place_name, data={"cols": {"place": place_name}})
                except Exception as exc:
                    counts["errors"] += 1
                    yield SyncEvent(kind="item", entity="place", action="failed",
                                    source_id=asset_id, title=place_name,
                                    detail=str(exc)[:200])

    try:
        preview = await preview_of(accounts, asset, cfg)
        cols = update_plan(asset, media, cfg, preview)
    except SyncError as exc:
        counts["errors"] += 1
        yield SyncEvent(kind="item", entity="media", action="failed",
                        source_id=asset_id, gramps_id=gid,
                        title=wanted_title(asset),
                        detail=str(exc)[:200])
        return
    tag_cols = id_tag_plan(asset, gid, cfg)
    pending = {**cols, **tag_cols}

    note_probe = None
    if cfg.note_sync_tag.lower() in tag_values(asset):
        try:
            note_probe = await sync_note(gramps, conn, asset_id, gid, media, apply=False)
        except Exception as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="note", action="failed",
                            source_id=asset_id, gramps_id=gid, title=media.get("desc"),
                            detail=str(exc)[:200])

    if not pending and note_probe is None:
        counts["skipped"] += 1
        return
    if not apply:
        if pending:
            yield SyncEvent(kind="item", entity="media", action="would_update",
                            source_id=asset_id, gramps_id=gid,
                            title=wanted_title(asset),
                            data={"cols": pending})
        if note_probe:
            yield note_probe
        return

    if pending and (selected is None or f"media:{asset_id}" in selected):
        if cols:
            if "title" in cols:
                media["desc"] = wanted_update_title(asset)
            if "date" in cols:
                media["date"] = wanted_date(asset)[0]
            if "file" in cols:
                media["path"], media["mime"] = gramps_file(asset, cfg, preview)
            if "link" in cols:
                _set_attr(media, "Immich ID", asset_id)
                if cfg.public_url:
                    _set_attr(media, "Immich URL", f"{cfg.public_url}/photos/{asset_id}")
            try:
                await gramps.update_media(media["handle"], media)
            except Exception as exc:
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, gramps_id=gid,
                                title=media.get("desc"), detail=str(exc)[:200])
                return
            if "file" in cols:
                counts["versions_updated"] += 1
                with conn:
                    conn.execute(
                        "UPDATE minted_media SET source_id=? "
                        "WHERE gramps_id=? AND source_system='immich'",
                        (asset_id, gid),
                    )
            elif "link" in cols:
                counts["links_updated"] += 1
            if "title" in cols:
                counts["titles_updated"] += 1
            if "date" in cols:
                counts["dates_updated"] += 1
        landed = dict(cols)
        if tag_cols:
            tag_error = await write_id_tag(accounts, asset, gid, cfg)
            if tag_error:
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="tag", action="failed",
                                source_id=asset_id, gramps_id=gid,
                                title=media.get("desc"), detail=tag_error)
            else:
                counts["id_tags_written"] += 1
                landed.update(tag_cols)
                record_error = await write_link_record(accounts, conn, asset, gid, cfg)
                if record_error:
                    counts["errors"] += 1
                    yield SyncEvent(kind="item", entity="tag", action="failed",
                                    source_id=asset_id, gramps_id=gid,
                                    title=media.get("desc"), detail=record_error)
        if landed:
            yield SyncEvent(kind="item", entity="media", action="updated",
                            source_id=asset_id, gramps_id=gid,
                            title=media["desc"], data={"cols": landed})

    # note-only rows select as "note:<id>"
    if note_probe and (selected is None or {f"media:{asset_id}", f"note:{asset_id}"} & selected):
        try:
            ev = await sync_note(gramps, conn, asset_id, gid, media, apply=True)
        except Exception as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="note", action="failed",
                            source_id=asset_id, gramps_id=gid, title=media.get("desc"),
                            detail=str(exc)[:200])
        else:
            if ev:
                counts["notes_synced"] += 1
                yield ev


async def sync_assets(
    gramps: GrampsClient,
    accounts: list[ImmichClient],
    conn: sqlite3.Connection,
    cfg: SyncImmichConfig,
    apply: bool = False,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """The Sync section's scan: create tagged unsynced assets, update registered media"""
    counts = new_counts()

    account_tags = []
    for client in accounts:
        account_tags.append((client, await client.find_tag(cfg.sync_tag)))
    if all(tag is None for _, tag in account_tags):
        raise SyncError(
            400,
            f"trigger tag {cfg.sync_tag!r} not found in any Immich account",
        )

    try:
        primary_of = {
            a["id"]: s.get("primaryAssetId")
            for client in accounts
            for s in await client.list_stacks()
            for a in (s.get("assets") or [])
        }
    except ImmichError as exc:
        raise SyncError(502, f"could not list Immich stacks: {exc.message}")
    stack_children = {aid for aid, primary in primary_of.items() if aid != primary}

    tagged, capped = [], False
    tagged_ids: set[str] = set()
    for client, tag in account_tags:
        if tag is None:
            continue
        items, was_capped = await _tagged_scope(client, tag["id"])
        capped = capped or was_capped
        for a in items:
            if a["id"] not in tagged_ids:
                tagged_ids.add(a["id"])
                tagged.append(a)

    rows = conn.execute(
        "SELECT gramps_id, source_id FROM minted_media WHERE source_system='immich'"
    ).fetchall()
    minted_ids = {r["source_id"] for r in rows}
    update_targets = [
        (r["gramps_id"], primary_of.get(r["source_id"]) or r["source_id"])
        for r in rows
    ]
    update_ids = {aid for _, aid in update_targets}

    scope = f"{len(tagged)} asset(s) tagged {cfg.sync_tag!r}; {len(rows)} synced media"
    if capped:
        scope += f" -- CAPPED at {_TAG_ASSET_CAP}, results are incomplete!"
    yield SyncEvent(kind="started", detail=scope)

    for client, tag in account_tags:
        if tag is None:
            label = getattr(client, "label", "") or "account"
            yield SyncEvent(
                kind="item", entity="media", action="skipped",
                detail=f"no trigger tag {cfg.sync_tag!r} in Immich account "
                       f"'{label}'; nothing scanned there")

    detail_ids = list(dict.fromkeys(
        [a["id"] for a in tagged if a["id"] not in stack_children] + sorted(update_ids)
    ))
    total = len(detail_ids) + len(tagged) + len(update_targets)
    done = 0

    def _progress(label: str) -> SyncEvent:
        return SyncEvent(kind="progress", detail=label,
                         data={"done": done, "total": total,
                               "percent": round(100 * done / total) if total else 100})

    detail_by_id: dict[str, dict | None] = {}
    for start in range(0, len(detail_ids), _DETAIL_BATCH):
        yield _progress("Reading photo details")
        batch = detail_ids[start:start + _DETAIL_BATCH]
        detail_by_id.update(await _merged_details(accounts, batch))
        done += len(batch)

    try:
        places = place_index(await gramps.list_places_full(), cfg)
    except Exception as exc:
        places = place_index([], cfg, failed=True)
        counts["errors"] += 1
        yield SyncEvent(kind="item", entity="place", action="failed",
                        detail=f"could not list Gramps places: {str(exc)[:180]}; "
                               "place links skipped this run")

    create_label = "Syncing new photos" if apply else "Checking new photos"
    for asset in tagged:
        yield _progress(create_label)
        done += 1
        asset_id = asset["id"]
        if asset_id in stack_children:
            primary = primary_of.get(asset_id)
            if primary in tagged_ids or primary in update_ids:
                continue  # the main represents the stack
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, title=asset.get("originalFileName"),
                            detail="tagged, but a hidden stack variant...tag the stack's main image")
            continue
        if asset_id in minted_ids or asset_id in update_ids:
            continue
        detail = detail_by_id.get(asset_id)
        if detail is None:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, title=asset.get("originalFileName"),
                            detail="asset detail fetch failed")
            continue
        asset = detail

        title = wanted_title(asset)
        date_obj, date_display = wanted_date(asset)
        cols = {"title": title, **({"date": date_display} if date_obj else {})}
        try:
            found = await resolve_place(gramps, asset, cfg, places)
        except SyncError as exc:
            found = None
            cols["place"] = exc.detail
        if found:
            cols["place"] = place_label(found[0])
        if not apply:
            yield SyncEvent(kind="item", entity="media", action="would_create",
                            source_id=asset_id, title=title, data={"cols": cols})
            continue
        if selected is not None and f"media:{asset_id}" not in selected:
            continue
        try:
            async for ev in sync_one_asset(gramps, accounts, conn, cfg, asset_id, places=places):
                if ev.kind == "item":
                    if ev.action == "failed":
                        counts["errors"] += 1
                    elif ev.entity == "place" and ev.action == "created":
                        counts["places_linked"] += 1
                    elif ev.entity == "tag" and ev.action == "created":
                        counts["id_tags_written"] += 1
                    elif ev.entity == "note" and ev.action in ("created", "updated"):
                        counts["notes_synced"] += 1
                    yield ev
                elif ev.kind == "summary":
                    if (ev.data or {}).get("created"):
                        counts["created"] += 1
        except SyncError as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, title=title, detail=exc.detail[:200])
        except Exception as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, title=title, detail=str(exc)[:200])

    effective_count: dict[str, int] = {}
    for _gid, aid in update_targets:
        effective_count[aid] = effective_count.get(aid, 0) + 1

    update_label = "Updating synced media" if apply else "Checking synced media"
    for gid, asset_id in update_targets:
        yield _progress(update_label)
        done += 1
        if effective_count[asset_id] > 1:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, gramps_id=gid,
                            detail="two synced media resolve to the same stack main, "
                                   "unstack them or fix the register before syncing")
            continue
        asset = detail_by_id.get(asset_id)
        if asset is None:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, gramps_id=gid,
                            detail="Immich asset lookup failed")
            continue
        if asset.get("isTrashed"):
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, gramps_id=gid,
                            title=asset.get("originalFileName"),
                            detail="asset is in the Immich trash")
            continue
        async for ev in update_synced(gramps, accounts, conn, cfg, gid, asset, None,
                                      places, apply, selected, counts):
            yield ev

    if total:
        yield _progress(update_label if update_targets else create_label)
    yield SyncEvent(kind="summary", data=counts)
