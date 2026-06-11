"""Immich → Gramps media sync (port of immich_to_gramps.py run_sync).

One async generator does everything the legacy script did per run:
1. New tagged assets become Gramps Media (path translation, Immich ID/URL
   attributes, optional date/place/description, face MediaRefs via the faces
   module so per-face pads apply).
2. Refresh passes keep already-synced media current: Sync/Date, Sync/Location
   (closest tagged place within 250 m), Sync/Description.

Preview is the same generator with apply=False. Minted media are recorded in
the minted_media table (the legacy minted.csv stays frozen as history).
"""

from __future__ import annotations

import logging
import math
import secrets
import sqlite3
from datetime import datetime
from typing import AsyncIterator

from ..core.clients import GrampsClient, ImmichClient
from ..core.config import SyncImmichConfig
from ..core.events import SyncEvent
from . import faces as faces_mod

log = logging.getLogger("bifrost.sync.immich")

# Metadata control tags (matched case-insensitively on full tag paths)
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

# Gramps date constants (gramps.gen.lib.date.Date)
MOD_REGULAR, MOD_BEFORE, MOD_AFTER, MOD_ABOUT = 0, 1, 2, 3
QUAL_REGULAR, QUAL_ESTIMATED, QUAL_CALCULATED = 0, 1, 2

MIME_FALLBACKS = {"IMAGE": "image/jpeg", "VIDEO": "video/mp4"}

CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
EARTH_RADIUS_KM = 6371.0
MAX_PLACE_DISTANCE_KM = 0.25  # 250 metres


# ---------------------------------------------------------------------------
# Pure helpers (ported verbatim from the legacy script)
# ---------------------------------------------------------------------------

def ellipsize(s: str, n: int = 64) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def get_asset_tag_values(asset: dict) -> set[str]:
    return {t["value"].lower() for t in asset.get("tags", []) if "value" in t}


def translate_path(original_path: str, path_mappings: tuple[dict, ...]) -> str:
    """Translate an Immich container path to a Gramps media path."""
    for m in path_mappings:
        ip = m.get("immich_prefix", "")
        gp = m.get("gramps_prefix", "")
        if ip and original_path.startswith(ip):
            return f"{gp}{original_path[len(ip):]}"
    relative = original_path.rsplit("/", 1)[-1]
    log.warning("Path %r matches no configured mapping; using filename only", original_path)
    return f"immich/{relative}"


def build_gramps_date(asset: dict) -> dict | None:
    """Build a Gramps Date dict from EXIF dateTimeOriginal + qualifier tags.

    Three independent tag groups (first match wins within a group):
      modifier:  date/approximate→ABOUT  date/before→BEFORE  date/after→AFTER
      quality:   date/calculated→CALCULATED  date/estimated→ESTIMATED
      precision: date/year→year only  date/month→month+year
                 (approximate with no precision tag strips the day — legacy)
    """
    exif = asset.get("exifInfo") or {}
    dt_str = exif.get("dateTimeOriginal") or asset.get("localDateTime")
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

    tags = get_asset_tag_values(asset)

    if TAG_DATE_APPROXIMATE in tags:
        modifier = MOD_ABOUT
    elif TAG_DATE_BEFORE in tags:
        modifier = MOD_BEFORE
    elif TAG_DATE_AFTER in tags:
        modifier = MOD_AFTER
    else:
        modifier = MOD_REGULAR

    if TAG_DATE_CALCULATED in tags:
        quality = QUAL_CALCULATED
    elif TAG_DATE_ESTIMATED in tags:
        quality = QUAL_ESTIMATED
    else:
        quality = QUAL_REGULAR

    if TAG_DATE_YEAR in tags:
        day, month = 0, 0
    elif TAG_DATE_MONTH in tags:
        day, month = 0, dt.month
    elif modifier == MOD_ABOUT:
        day, month = 0, dt.month
    else:
        day, month = dt.day, dt.month

    return {
        "_class": "Date",
        "dateval": [day, month, dt.year, False],
        "modifier": modifier,
        "quality": quality,
        "text": "",
    }


def format_gramps_date(date_obj: dict | None) -> str:
    if not date_obj:
        return "(none)"
    dv = date_obj.get("dateval") or []
    if len(dv) < 3:
        return "(none)"
    day, month, year = dv[0], dv[1], dv[2]
    if year == 0 and month == 0 and day == 0:
        return "(none)"
    if day == 0 and month == 0:
        date_str = f"{year}"
    elif day == 0:
        date_str = f"{year}-{month:02d}"
    else:
        date_str = f"{year}-{month:02d}-{day:02d}"
    mod = {1: "Before ", 2: "After ", 3: "About ", 4: "Range ", 5: "Span "}.get(
        date_obj.get("modifier", 0), "")
    qual = {1: "Est. ", 2: "Calc. "}.get(date_obj.get("quality", 0), "")
    return f"{qual}{mod}{date_str}"


def get_asset_coords(asset: dict) -> tuple[float, float] | None:
    exif = asset.get("exifInfo") or {}
    lat, lon = exif.get("latitude"), exif.get("longitude")
    if lat is None or lon is None:
        return None
    return (round(lat, 4), round(lon, 4))


def parse_gramps_coord(value: str) -> float | None:
    """Plain decimals plus N/S/E/W-prefixed values (e.g. 'N45.5', 'W92.9')."""
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


def find_closest_place(lat: float, lon: float, places: list[dict]) -> tuple[dict, float] | None:
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


def generate_gramps_id(existing: set[str], length: int = 6) -> str:
    for _ in range(1000):
        candidate = "".join(secrets.choice(CHARSET) for _ in range(length))
        if candidate not in existing:
            existing.add(candidate)
            return candidate
    raise RuntimeError("Failed to generate gramps_id")


def generate_handle() -> str:
    return "".join(secrets.choice(CHARSET) for _ in range(16))


# ---------------------------------------------------------------------------
# The sync generator
# ---------------------------------------------------------------------------

async def sync(
    gramps: GrampsClient,
    immich: ImmichClient,
    conn: sqlite3.Connection,
    cfg: SyncImmichConfig,
    apply: bool,
) -> AsyncIterator[SyncEvent]:
    counts = {"created": 0, "skipped": 0, "faces_linked": 0,
              "dates_updated": 0, "places_linked": 0, "descs_updated": 0,
              "errors": 0}

    # --- Gather inputs ---
    tag_ids = []
    for name in cfg.sync_tags:
        tid = await immich.resolve_tag_id(name)
        if tid:
            tag_ids.append(tid)
    if not tag_ids:
        yield SyncEvent(kind="error", detail="no sync tags found in Immich")
        yield SyncEvent(kind="summary", data=counts)
        return

    asset_ids: list[str] = []
    seen: set[str] = set()
    for tid in tag_ids:
        for item in await immich.search_assets_by_tag(tid):
            if item["id"] not in seen:
                seen.add(item["id"])
                asset_ids.append(item["id"])
    # Search results lack tags/EXIF — enrich with full asset fetches.
    assets = list(await faces_mod._gather_limited(
        [immich.get_asset(a) for a in asset_ids]
    ))
    yield SyncEvent(kind="started", detail=f"{len(assets)} tagged asset(s) in Immich")

    synced = await faces_mod.synced_immich_media(gramps)
    existing_ids = await gramps.list_media_gramps_ids()
    links = faces_mod.list_links(conn)
    by_immich = {e["immich_person_id"]: e for e in links}

    places_with_coords: list[dict] = []
    if cfg.place_tag_handle:
        places_with_coords = [
            p for p in await gramps.list_places_full()
            if cfg.place_tag_handle in p.get("tag_list", [])
            and p.get("lat") and p.get("long")
        ]
    yield SyncEvent(
        kind="started",
        detail=f"{len(synced)} already synced; {len(places_with_coords)} linkable places",
    )

    # --- New assets → Media ---
    for asset in assets:
        asset_id = asset["id"]
        filename = asset.get("originalFileName") or f"Immich {asset_id[:8]}"
        if asset_id in synced:
            counts["skipped"] += 1
            continue

        tags = get_asset_tag_values(asset)
        desc_text = ""
        if TAG_SYNC_DESCRIPTION in tags:
            desc_text = ((asset.get("exifInfo") or {}).get("description") or "").strip()
        title = desc_text or filename
        gramps_id = generate_gramps_id(existing_ids)
        handle = generate_handle()
        gramps_path = translate_path(asset.get("originalPath", ""), cfg.path_mappings)
        mime = asset.get("originalMimeType") or MIME_FALLBACKS.get(
            asset.get("type", "IMAGE"), "application/octet-stream")

        media_obj = {
            "_class": "Media",
            "handle": handle,
            "gramps_id": gramps_id,
            "desc": title,
            "path": gramps_path,
            "mime": mime,
            "private": False,
            "change": int(datetime.utcnow().timestamp()),
            "attribute_list": [
                {"_class": "Attribute", "type": "Immich ID", "value": asset_id,
                 "private": False, "citation_list": [], "note_list": []},
                {"_class": "Attribute", "type": "Immich URL",
                 "value": f"{cfg.public_url}/photos/{asset_id}",
                 "private": False, "citation_list": [], "note_list": []},
            ],
        }

        cols: dict = {}
        if TAG_SYNC_DATE in tags:
            gramps_date = build_gramps_date(asset)
            if gramps_date:
                media_obj["date"] = gramps_date
                cols["date"] = format_gramps_date(gramps_date)

        place_to_link = None
        if TAG_SYNC_LOCATION in tags and places_with_coords:
            coords = get_asset_coords(asset)
            if coords:
                result = find_closest_place(coords[0], coords[1], places_with_coords)
                if result:
                    place_to_link = result[0]
                    cols["place"] = place_to_link.get("name", {}).get("value", "?")
        if desc_text:
            cols["description"] = "used as title"
        elif TAG_SYNC_DESCRIPTION in tags:
            cols["description"] = "tagged, empty"

        if apply:
            try:
                await gramps.create_media(media_obj)
            except Exception as exc:  # noqa: BLE001
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, title=title, detail=str(exc))
                continue
            synced[asset_id] = media_obj
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO minted_media"
                    " (gramps_id, source_system, source_id, title, minted_at)"
                    " VALUES (?, 'immich', ?, ?, ?)",
                    (gramps_id, asset_id, title,
                     datetime.now().isoformat(timespec="seconds")),
                )
        counts["created"] += 1
        yield SyncEvent(
            kind="item", entity="media",
            action="created" if apply else "would_create",
            source_id=asset_id, gramps_id=gramps_id, title=ellipsize(title),
            data={"path": gramps_path, "mime": mime, "cols": cols},
        )

        # Faces of linked people, via the faces module (per-face pads apply)
        is_manual = TAG_SYNC_MANUAL_FACES in tags
        for face in await immich.get_faces(asset_id):
            ipid = (face.get("person") or {}).get("id")
            link = by_immich.get(ipid) if ipid else None
            if not link:
                continue
            p_handle = link["gramps_handle"]
            pad = faces_mod.effective_pad(conn, p_handle, asset_id, is_manual)
            face_title = (face.get("person") or {}).get("name") or ipid[:8]
            if apply:
                try:
                    await faces_mod.apply_face(
                        gramps, immich, conn, p_handle, asset_id, pad,
                        media_handle=handle,
                    )
                except Exception as exc:  # noqa: BLE001
                    counts["errors"] += 1
                    yield SyncEvent(kind="item", entity="face", action="failed",
                                    source_id=asset_id, title=face_title,
                                    detail=str(exc))
                    continue
            counts["faces_linked"] += 1
            yield SyncEvent(
                kind="item", entity="face",
                action="created" if apply else "would_create",
                source_id=asset_id,
                title=f"{link.get('label') or face_title} on '{ellipsize(title, 40)}'",
                data={"cols": {"pad": f"{int(pad * 100)}%"}},
            )

        # Closest-place link for the new media
        if place_to_link is not None:
            place_name = place_to_link.get("name", {}).get("value", "?")
            if apply:
                refs = place_to_link.setdefault("media_list", [])
                if not any(mr.get("ref") == handle for mr in refs):
                    refs.append({
                        "_class": "MediaRef", "ref": handle, "rect": [],
                        "attribute_list": [], "citation_list": [],
                        "note_list": [], "private": False,
                    })
                    try:
                        await gramps.update_place(place_to_link["handle"], place_to_link)
                    except Exception as exc:  # noqa: BLE001
                        counts["errors"] += 1
                        yield SyncEvent(kind="item", entity="place", action="failed",
                                        source_id=asset_id, title=place_name,
                                        detail=str(exc))
                        continue
            counts["places_linked"] += 1
            yield SyncEvent(
                kind="item", entity="place",
                action="updated" if apply else "would_update",
                source_id=asset_id, gramps_id=place_to_link.get("gramps_id"),
                title=ellipsize(title, 40),
                data={"cols": {"place": place_name}},
            )

    # --- Refresh passes for already-synced assets ---
    for asset in assets:
        asset_id = asset["id"]
        media = synced.get(asset_id)
        if media is None:
            continue
        tags = get_asset_tag_values(asset)
        title = asset.get("originalFileName") or asset_id[:8]
        gramps_id = media.get("gramps_id", "?")

        # Sync/Date refresh
        if TAG_SYNC_DATE in tags:
            new_date = build_gramps_date(asset)
            cur = media.get("date") or {}
            differs = bool(new_date) and (
                (new_date.get("dateval") or []) != (cur.get("dateval") or [])
                or new_date.get("modifier", 0) != cur.get("modifier", 0)
                or new_date.get("quality", 0) != cur.get("quality", 0)
            )
            if differs:
                date_change = f"{format_gramps_date(cur)} → {format_gramps_date(new_date)}"
                if apply:
                    try:
                        media["date"] = new_date
                        media["change"] = int(datetime.utcnow().timestamp())
                        await gramps.update_media(media["handle"], media)
                    except Exception as exc:  # noqa: BLE001
                        counts["errors"] += 1
                        yield SyncEvent(kind="item", entity="media", action="failed",
                                        source_id=asset_id, title=title, detail=str(exc))
                        continue
                counts["dates_updated"] += 1
                yield SyncEvent(kind="item", entity="media",
                                action="updated" if apply else "would_update",
                                source_id=asset_id, gramps_id=gramps_id,
                                title=ellipsize(title),
                                data={"cols": {"date": date_change}})

        # Sync/Location refresh
        if TAG_SYNC_LOCATION in tags and places_with_coords:
            coords = get_asset_coords(asset)
            result = (find_closest_place(coords[0], coords[1], places_with_coords)
                      if coords else None)
            if result:
                place, _dist = result
                refs = place.setdefault("media_list", [])
                if not any(mr.get("ref") == media["handle"] for mr in refs):
                    place_name = place.get("name", {}).get("value", "?")
                    if apply:
                        refs.append({
                            "_class": "MediaRef", "ref": media["handle"], "rect": [],
                            "attribute_list": [], "citation_list": [],
                            "note_list": [], "private": False,
                        })
                        try:
                            await gramps.update_place(place["handle"], place)
                        except Exception as exc:  # noqa: BLE001
                            counts["errors"] += 1
                            yield SyncEvent(kind="item", entity="place", action="failed",
                                            source_id=asset_id, title=place_name,
                                            detail=str(exc))
                            continue
                    counts["places_linked"] += 1
                    yield SyncEvent(kind="item", entity="place",
                                    action="updated" if apply else "would_update",
                                    source_id=asset_id, gramps_id=place.get("gramps_id"),
                                    title=ellipsize(title, 40),
                                    data={"cols": {"place": place_name}})

        # Sync/Description refresh
        if TAG_SYNC_DESCRIPTION in tags:
            new_desc = ((asset.get("exifInfo") or {}).get("description") or "").strip()
            if new_desc and new_desc != (media.get("desc") or "").strip():
                snippet = new_desc if len(new_desc) <= 80 else new_desc[:77] + "..."
                if apply:
                    try:
                        media["desc"] = new_desc
                        media["change"] = int(datetime.utcnow().timestamp())
                        await gramps.update_media(media["handle"], media)
                    except Exception as exc:  # noqa: BLE001
                        counts["errors"] += 1
                        yield SyncEvent(kind="item", entity="media", action="failed",
                                        source_id=asset_id, title=title, detail=str(exc))
                        continue
                counts["descs_updated"] += 1
                yield SyncEvent(kind="item", entity="media",
                                action="updated" if apply else "would_update",
                                source_id=asset_id, gramps_id=gramps_id,
                                title=ellipsize(title),
                                data={"cols": {"description": snippet}})

    yield SyncEvent(kind="summary", data=counts)
