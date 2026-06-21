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
import re
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

# A stack counts as a version set only if a member carries a tag with this path
# prefix (written when a photo is opted into versioning). Keeps the pre-existing
# burst/RAW/sequential stacks out of scope. See docs/IMMICH_VERSIONING.md §11.
TAG_GRAMPS_BASE_PREFIX = "gramps/base/"

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

# Object types that can carry a face MediaRef (rect) back to a media object —
# cleared when a version change replaces the image. Mirrors sync_paperless.
BACKLINK_OBJ_TYPES = {
    "person": "people", "family": "families", "event": "events",
    "citation": "citations", "source": "sources", "place": "places",
}

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


MANUAL_ID_RE = re.compile(rf"^[{CHARSET}]{{6}}$")


def validate_manual_ids(
    manual_ids: dict | None, taken: set[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Split a {source_id: chosen_id} map into (valid, rejected{source_id: reason}).

    A valid id matches the media-id format (6 chars of the safe alphabet), is not
    already in Gramps, and is unique within the batch. Blank entries are ignored
    (that asset just gets an auto id). Reserved-but-unminted ids are accepted —
    `taken` is the set of ids already realized in Gramps, not the reservation pool.
    """
    valid: dict[str, str] = {}
    rejected: dict[str, str] = {}
    claimed: set[str] = set()
    for sid, raw in (manual_ids or {}).items():
        gid = (raw or "").strip()
        if not gid:
            continue
        if not MANUAL_ID_RE.match(gid):
            rejected[sid] = f"invalid id '{gid}' — need 6 chars from {CHARSET}"
        elif gid in taken:
            rejected[sid] = f"id '{gid}' is already in use"
        elif gid in claimed:
            rejected[sid] = f"id '{gid}' assigned to more than one asset"
        else:
            claimed.add(gid)
            valid[sid] = gid
    return valid, rejected


# ---------------------------------------------------------------------------
# Version state (docs/IMMICH_VERSIONING.md). An Immich stack is one logical
# photo's version set; its primaryAssetId is the version displayed in Gramps.
# ---------------------------------------------------------------------------

def _get_iversion(conn: sqlite3.Connection, gramps_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM immich_versions WHERE gramps_id=?", (gramps_id,)
    ).fetchone()


async def _stack_is_managed(immich: ImmichClient, conn: sqlite3.Connection,
                            asset: dict, gramps_id: str) -> bool:
    """Whether Bifrost manages this stack as a version set. True if: an existing
    immich_versions row; the iterated (displayed) asset carries a Gramps/Base/*
    tag (the fast path once propagated); or — the opt-in case — a
    `Gramps/Base/<gramps_id>` tag exists at all, since Peter may tag ANY member
    (often a non-displayed version), not necessarily the synced one. Pre-existing
    burst/RAW/sequential stacks have none and are ignored until opted in."""
    if _get_iversion(conn, gramps_id) is not None:
        return True
    if any(v.startswith(TAG_GRAMPS_BASE_PREFIX) for v in get_asset_tag_values(asset)):
        return True
    return await immich.resolve_tag_id(f"Gramps/Base/{gramps_id}") is not None


def _set_iversion(conn: sqlite3.Connection, gramps_id: str, stack_id: str,
                  current_asset_id: str, current_checksum: str, member_count: int) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO immich_versions"
            " (gramps_id, stack_id, current_asset_id, current_checksum, member_count, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (gramps_id, stack_id, current_asset_id, current_checksum, member_count,
             datetime.now().isoformat(timespec="seconds")),
        )


def _set_media_attr(media: dict, attr_type: str, value: str) -> None:
    """Overwrite an existing attribute's value in place, or append it."""
    for a in media.get("attribute_list", []):
        if a.get("type") == attr_type:
            a["value"] = value
            return
    media.setdefault("attribute_list", []).append(
        {"_class": "Attribute", "type": attr_type, "value": value,
         "private": False, "citation_list": [], "note_list": []})


def _path_mapping_matches(original_path: str, path_mappings: tuple[dict, ...]) -> bool:
    """True if some mapping prefix matches — i.e. translate_path won't fall back
    to the bare 'immich/<filename>' that 404s on the read-only Gramps mount."""
    return any(original_path.startswith(m.get("immich_prefix", ""))
               for m in path_mappings if m.get("immich_prefix"))


async def _persist_stack(
    immich: ImmichClient, conn: sqlite3.Connection, cfg: SyncImmichConfig,
    gramps_id: str, stack_id: str, current_asset_id: str, current_checksum: str,
) -> None:
    """Apply-only: record a managed stack's state and keep it in the sync universe.

    Propagates the configured sync tags + a `Gramps/Base/<id>` tag onto EVERY
    stack member, so (a) the displayed version is always tagged and a full sync
    keeps refreshing it (no date/place regression after a promotion), (b) any
    member promoted later is already in scope, and (c) the version set is
    self-describing in Immich and rebuildable if Bifrost's DB is lost. Then it
    refreshes immich_version_members and upserts the immich_versions row.
    """
    stack = await immich.get_stack(stack_id)
    members = stack.get("assets", [])
    member_ids = [m["id"] for m in members]

    base_value = f"Gramps/Base/{gramps_id}"
    await immich.upsert_tags([base_value])  # idempotent; sync tags already exist
    if member_ids:
        for value in (*cfg.sync_tags, base_value):
            tid = await immich.resolve_tag_id(value)
            if tid:
                await immich.tag_assets(tid, member_ids)

    # Preserve any role/label the UI already set on a member across this refresh.
    prev = {r["asset_id"]: r for r in conn.execute(
        "SELECT asset_id, role, label FROM immich_version_members WHERE gramps_id=?",
        (gramps_id,)).fetchall()}
    with conn:
        conn.execute("DELETE FROM immich_version_members WHERE gramps_id=?", (gramps_id,))
        conn.executemany(
            "INSERT INTO immich_version_members"
            " (gramps_id, asset_id, checksum, role, label, seq) VALUES (?, ?, ?, ?, ?, ?)",
            [(gramps_id, m["id"], m.get("checksum", ""),
              prev[m["id"]]["role"] if m["id"] in prev else None,
              prev[m["id"]]["label"] if m["id"] in prev else None, seq)
             for seq, m in enumerate(members, start=1)],
        )
    _set_iversion(conn, gramps_id, stack_id, current_asset_id, current_checksum, len(members))


# ---------------------------------------------------------------------------
# The sync generator
# ---------------------------------------------------------------------------

async def sync(
    gramps: GrampsClient,
    immich: ImmichClient,
    conn: sqlite3.Connection,
    cfg: SyncImmichConfig,
    apply: bool,
    manual_ids: dict[str, str] | None = None,
    versions_only: bool = False,
) -> AsyncIterator[SyncEvent]:
    # versions_only: run ONLY the version phase (repoint Gramps to the stack's
    # displayed/primary asset). No create / date / place / description work —
    # the lean path for the unattended scheduled run, mirroring sync_paperless.
    counts = {"created": 0, "skipped": 0, "faces_linked": 0,
              "dates_updated": 0, "places_linked": 0, "descs_updated": 0,
              "baselined": 0, "versions_updated": 0,
              "faces_cleared": 0, "faces_rederived": 0,
              "stacks_seen": 0, "stacks_managed": 0, "errors": 0}

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
    # Non-displayed members of a managed version set carry the sync tag (so they
    # stay discoverable for the version phase), but they are VERSIONS of an
    # existing photo — never create them as their own Gramps media. The displayed
    # member is in `synced` already; the others are skipped below.
    version_member_ids = {r["asset_id"] for r in
        conn.execute("SELECT asset_id FROM immich_version_members").fetchall()}
    existing_ids = await gramps.list_media_gramps_ids()
    # Manual ids: validate against what's really in Gramps, then keep the auto
    # generator away from both reserved ids and the chosen manual ids.
    from . import idgen  # lazy: idgen imports generate_gramps_id from this module
    taken = set(existing_ids)
    valid_manual, rejected_manual = validate_manual_ids(manual_ids, taken)
    existing_ids |= idgen.unminted_reserved(conn)
    existing_ids |= set(valid_manual.values())
    links = faces_mod.list_links(conn)
    by_immich = {e["immich_person_id"]: e for e in links}

    places_with_coords: list[dict] = []
    if cfg.place_tag_handle and not versions_only:
        places_with_coords = [
            p for p in await gramps.list_places_full()
            if cfg.place_tag_handle in p.get("tag_list", [])
            and p.get("lat") and p.get("long")
        ]
    yield SyncEvent(
        kind="started",
        detail=f"{len(synced)} already synced; {len(places_with_coords)} linkable places",
    )

    # --- New assets → Media (manual-id assets first, so auto ids never race them) ---
    assets.sort(key=lambda a: 0 if a["id"] in valid_manual else 1)
    for asset in (assets if not versions_only else []):
        asset_id = asset["id"]
        filename = asset.get("originalFileName") or f"Immich {asset_id[:8]}"
        if asset_id in synced:
            counts["skipped"] += 1
            continue
        if asset_id in version_member_ids:
            continue  # a non-displayed version of a managed photo, not a new item
        if asset_id in rejected_manual:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, title=filename,
                            detail=rejected_manual[asset_id])
            continue

        tags = get_asset_tag_values(asset)
        desc_text = ""
        if TAG_SYNC_DESCRIPTION in tags:
            desc_text = ((asset.get("exifInfo") or {}).get("description") or "").strip()
        title = desc_text or filename
        gramps_id = valid_manual.get(asset_id) or generate_gramps_id(existing_ids)
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

        if apply:
            try:
                await gramps.create_media(media_obj)
            except Exception as exc:  # noqa: BLE001
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, title=title, detail=str(exc))
                continue
            synced[asset_id] = media_obj
            idgen.mark_minted(conn, gramps_id)  # no-op unless it was a reserved id
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
    for asset in (assets if not versions_only else []):
        asset_id = asset["id"]
        media = synced.get(asset_id)
        if media is None:
            continue
        tags = get_asset_tag_values(asset)
        # Label the row by the media's current Gramps title (its description),
        # like the create rows do — the filename is rarely how Peter thinks of it.
        filename = asset.get("originalFileName") or asset_id[:8]
        title = (media.get("desc") or "").strip() or filename
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

    # ============ Version phase: stack primary → displayed version ============
    # An Immich stack groups one logical photo's versions; its primaryAssetId is
    # the version shown in Gramps. `synced` is keyed on the Immich ID attribute,
    # so the asset_id we point at IS what Gramps currently shows; the stack is in
    # sync when that asset is the stack primary. A different primary = a deliberate
    # promotion → repoint the SAME Gramps media: the base id and handle stay
    # FROZEN; only path/mime + the Immich ID/URL attributes change. Now-invalid
    # face rects are cleared and left PENDING (re-derivation is phase 5). The
    # opt-in guard keeps the pre-existing burst/RAW stacks out of scope.
    for asset in assets:
        asset_id = asset["id"]
        media = synced.get(asset_id)
        if media is None:
            continue
        stack = asset.get("stack")
        if not stack:
            continue
        counts["stacks_seen"] += 1
        gramps_id = media.get("gramps_id", "?")
        if not await _stack_is_managed(immich, conn, asset, gramps_id):
            continue  # pre-existing burst/RAW stack, not opted into versioning
        counts["stacks_managed"] += 1
        stack_id = stack.get("id")
        member_count = stack.get("assetCount", 0)
        primary = stack.get("primaryAssetId")
        title = ((media.get("desc") or "").strip()
                 or asset.get("originalFileName") or asset_id[:8])
        tracked = _get_iversion(conn, gramps_id)

        # In sync: Gramps already shows the stack primary. First sight = baseline;
        # a later membership change re-propagates tags and refreshes the row.
        if primary == asset_id:
            if tracked is None:
                if apply:
                    await _persist_stack(immich, conn, cfg, gramps_id, stack_id,
                                         asset_id, asset.get("checksum", ""))
                counts["baselined"] += 1
            elif apply and tracked["member_count"] != member_count:
                await _persist_stack(immich, conn, cfg, gramps_id, stack_id,
                                     asset_id, asset.get("checksum", ""))
            continue

        # Divergence: a different member is the displayed/primary version.
        try:
            new = await immich.get_asset(primary)
        except Exception as exc:  # noqa: BLE001 — e.g. the primary was deleted
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=primary, gramps_id=gramps_id, title=ellipsize(title),
                            detail=f"displayed version {primary[:8]} unavailable: {exc}")
            continue

        original_path = new.get("originalPath", "")
        if not _path_mapping_matches(original_path, cfg.path_mappings):
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=primary, gramps_id=gramps_id, title=ellipsize(title),
                            detail=f"path {original_path!r} is under no configured mount")
            continue
        new_path = translate_path(original_path, cfg.path_mappings)
        new_mime = new.get("originalMimeType") or MIME_FALLBACKS.get(
            new.get("type", "IMAGE"), "application/octet-stream")

        fresh = await gramps.get_media_by_gramps_id(gramps_id)
        if not fresh:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=primary, gramps_id=gramps_id, title=ellipsize(title),
                            detail=f"no Gramps media {gramps_id}")
            continue

        vcols: dict = {"version": "repointed" if apply else "would repoint",
                       "from": asset_id[:8], "to": primary[:8]}
        if fresh.get("path") != new_path or fresh.get("mime") != new_mime:
            vcols["path/mime"] = "updated"

        # Clear now-invalid face rects on every backlinked object (the pixels
        # changed). Counted in preview too; only nulled+saved under apply.
        cleared = 0
        backlinks = await gramps.get_media_backlinks(fresh["handle"])
        for bl_type, api_path in BACKLINK_OBJ_TYPES.items():
            for obj_handle in backlinks.get(bl_type, []):
                obj = await gramps.get_object(api_path, obj_handle)
                modified = False
                for mref in obj.get("media_list", []):
                    if mref.get("ref") == fresh["handle"] and mref.get("rect"):
                        cleared += 1
                        if apply:
                            mref["rect"] = None
                            modified = True
                if modified and apply:
                    await gramps.update_object(api_path, obj_handle, obj)
        if cleared:
            counts["faces_cleared"] += cleared

        re_derived = 0
        if apply:
            _set_media_attr(fresh, "Immich ID", primary)
            _set_media_attr(fresh, "Immich URL", f"{cfg.public_url}/photos/{primary}")
            fresh["path"] = new_path
            fresh["mime"] = new_mime
            fresh["change"] = int(datetime.utcnow().timestamp())
            await gramps.update_media(fresh["handle"], fresh)
            # Tag the new primary into the sync universe + refresh row/members.
            await _persist_stack(immich, conn, cfg, gramps_id, stack_id, primary,
                                 new.get("checksum", ""))
            # Best-effort re-derivation: re-draw the faces of LINKED people that
            # Immich still detects on the new primary (person ids usually carry
            # across a rescan via Immich recognition). Unmatched faces and any
            # non-person rects stay PENDING — cleared, never silently mis-placed.
            new_is_manual = TAG_SYNC_MANUAL_FACES in get_asset_tag_values(new)
            for face in await immich.get_faces(primary):
                ipid = (face.get("person") or {}).get("id")
                link = by_immich.get(ipid) if ipid else None
                if not link:
                    continue
                pad = faces_mod.effective_pad(conn, link["gramps_handle"], primary, new_is_manual)
                try:
                    await faces_mod.apply_face(gramps, immich, conn, link["gramps_handle"],
                                               primary, pad, media_handle=fresh["handle"])
                except Exception:  # noqa: BLE001 — best effort; leave pending
                    continue
                re_derived += 1
            counts["faces_rederived"] += re_derived

        if cleared or re_derived:
            pending = max(0, cleared - re_derived)
            vcols["faces"] = f"{cleared} cleared / {re_derived} re-derived / {pending} pending"

        counts["versions_updated"] += 1
        yield SyncEvent(
            kind="item", entity="media",
            action="updated" if apply else "would_update",
            source_id=primary, gramps_id=gramps_id, title=ellipsize(title),
            data={"cols": vcols},
        )

    yield SyncEvent(kind="summary", data=counts)


# ---------------------------------------------------------------------------
# Interactive version management (the VERSIONS strip — docs/IMMICH_VERSIONING.md
# §8). Bifrost is the cockpit; the durable state (stack, primaryAssetId, role
# tags) lives in Immich. These single-photo ops back the UI; promotion itself
# reuses set_stack_primary + the versions_only sync.
# ---------------------------------------------------------------------------

# Role → the Immich tag that carries it (kind is provenance, set explicitly).
VERSION_ROLES = {
    "original": "Gramps/Role/Original",
    "ai": "Gramps/Role/AI",
    "crop": "Gramps/Role/Crop",
    "duplicate": "Gramps/Role/Duplicate",
    "verso": "Gramps/Role/Verso",
}
TAG_GRAMPS_ROLE_PREFIX = "gramps/role/"


async def version_set(
    immich: ImmichClient, gramps: GrampsClient, conn: sqlite3.Connection,
    cfg: SyncImmichConfig, asset_id: str,
) -> dict:
    """The version set for the photo currently displayed as `asset_id` — the
    live stack merged with Bifrost's role/label/seq cache. `versioned=False`
    when the asset is not in a stack."""
    asset = await immich.get_asset(asset_id)
    stack = asset.get("stack")
    if not stack:
        return {"versioned": False}
    full = await immich.get_stack(stack["id"])
    members = full.get("assets", [])
    primary = full.get("primaryAssetId")

    synced = await faces_mod.synced_immich_media(gramps)
    gramps_id = next((synced[m["id"]].get("gramps_id")
                      for m in members if m["id"] in synced), None)
    managed = bool(gramps_id) and await _stack_is_managed(immich, conn, asset, gramps_id)
    cache = {r["asset_id"]: r for r in conn.execute(
        "SELECT asset_id, role, label, seq FROM immich_version_members WHERE gramps_id=?",
        (gramps_id,)).fetchall()} if gramps_id else {}

    out = []
    for i, m in enumerate(members):
        row = cache.get(m["id"])
        out.append({
            "asset_id": m["id"],
            "filename": m.get("originalFileName"),
            "is_displayed": m["id"] == primary,
            "role": row["role"] if row else None,
            "label": row["label"] if row else None,
            "seq": row["seq"] if row else i + 1,
            "thumb_url": f"/faces/api/thumb/asset/{m['id']}",
        })
    out.sort(key=lambda x: x["seq"])
    return {"versioned": True, "managed": managed, "gramps_id": gramps_id,
            "stack_id": stack["id"], "primary_asset_id": primary, "members": out}


async def set_role(
    immich: ImmichClient, conn: sqlite3.Connection,
    gramps_id: str, asset_id: str, role: str | None,
) -> dict:
    """Mark a member's kind. Writes the durable `Gramps/Role/*` Immich tag
    (removing any prior role tag) and mirrors it into the members cache.
    role=None clears the kind."""
    if role is not None and role not in VERSION_ROLES:
        raise ValueError(f"unknown role {role!r}")

    asset = await immich.get_asset(asset_id)
    for t in asset.get("tags", []):
        val = (t.get("value") or t.get("name") or "").lower()
        if val.startswith(TAG_GRAMPS_ROLE_PREFIX) and t.get("id"):
            await immich.untag_assets(t["id"], [asset_id])
    if role is not None:
        value = VERSION_ROLES[role]
        await immich.upsert_tags([value])
        tid = await immich.resolve_tag_id(value)
        if tid:
            await immich.tag_assets(tid, [asset_id])
    with conn:
        conn.execute(
            "UPDATE immich_version_members SET role=? WHERE gramps_id=? AND asset_id=?",
            (role, gramps_id, asset_id))
    return {"asset_id": asset_id, "role": role}


def set_label(conn: sqlite3.Connection, gramps_id: str, asset_id: str,
              label: str | None) -> dict:
    """Set a member's free-text note (Bifrost-owned)."""
    label = (label or "").strip() or None
    with conn:
        conn.execute(
            "UPDATE immich_version_members SET label=? WHERE gramps_id=? AND asset_id=?",
            (label, gramps_id, asset_id))
    return {"asset_id": asset_id, "label": label}


async def adopt(
    immich: ImmichClient, conn: sqlite3.Connection, cfg: SyncImmichConfig,
    gramps_id: str, displayed_asset_id: str, add_asset_ids: list[str],
) -> dict:
    """Fold already-uploaded asset(s) into a NEW stack with the synced photo,
    opting it into versioning. The synced (displayed) asset is listed first so
    it stays the primary; then propagate tags + baseline via _persist_stack.
    Assumes the displayed asset is not already stacked (UI guards that)."""
    ids = [displayed_asset_id, *[a for a in add_asset_ids if a != displayed_asset_id]]
    if len(ids) < 2:
        raise ValueError("need at least one other asset to form a version set")
    stack = await immich.create_stack(ids)
    displayed = await immich.get_asset(displayed_asset_id)
    await _persist_stack(immich, conn, cfg, gramps_id, stack["id"],
                         displayed_asset_id, displayed.get("checksum", ""))
    return {"stack_id": stack["id"], "members": ids, "primary_asset_id": displayed_asset_id}
