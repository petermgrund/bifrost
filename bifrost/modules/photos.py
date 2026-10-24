"""Immich photos curated for Gramps"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from datetime import date, datetime, timezone
from typing import AsyncIterator

from ..core import settings as ui_settings
from ..core.clients import GrampsClient, ImmichClient
from ..core.clients.immich import ImmichError
from ..core.config import SyncImmichConfig
from ..core.events import SyncEvent
from . import codes, photo_collections
from . import sync_immich as si
from .sync_immich import SyncError, compose_description
from .sync_paperless import format_gramps_date

PAGE_SIZE = 24
PRECISIONS = ("exact", "month", "year")
MODIFIERS = ("regular", "about", "before", "after", "decade", "span")
RANGES = ("decade", "span")
SPAN_MAX = 999
QUALITIES = ("regular", "estimated", "calculated")
MODIFIER_TAGS = {"about": si.TAG_DATE_APPROXIMATE, "before": si.TAG_DATE_BEFORE,
                 "after": si.TAG_DATE_AFTER, "decade": si.TAG_DATE_DECADE}
QUALITY_TAGS = {"calculated": si.TAG_DATE_CALCULATED, "estimated": si.TAG_DATE_ESTIMATED}
PRECISION_TAGS = {"year": si.TAG_DATE_YEAR, "month": si.TAG_DATE_MONTH}
DATE_TAGS = set(MODIFIER_TAGS.values()) | set(QUALITY_TAGS.values()) | set(PRECISION_TAGS.values())
CANONICAL = {
    si.TAG_SYNC_DATE: "Sync/Date", si.TAG_SYNC_DESCRIPTION: "Sync/Description",
    si.TAG_SYNC_LOCATION: "Sync/Location", si.TAG_SYNC_MANUAL_FACES: "Sync/ManualFaces",
    si.TAG_DATE_APPROXIMATE: "Date/Approximate", si.TAG_DATE_BEFORE: "Date/Before",
    si.TAG_DATE_AFTER: "Date/After", si.TAG_DATE_ESTIMATED: "Date/Estimated",
    si.TAG_DATE_CALCULATED: "Date/Calculated", si.TAG_DATE_YEAR: "Date/Year",
    si.TAG_DATE_MONTH: "Date/Month", si.TAG_DATE_DECADE: "Date/Decade",
}
_DATE_RE = re.compile(r"^\s*(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?\s*$")
_LINK_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
LINK_MAX = 2000
EMPTY_DATE = {"_class": "Date", "dateval": [0, 0, 0, False], "modifier": 0, "quality": 0, "text": ""}
_MODIFIER_NAMES = {v: k for k, v in si._MODIFIERS.items()}
_QUALITY_NAMES = {v: k for k, v in si._QUALITIES.items()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_date_value(text: str) -> tuple[str, str] | None:
    """'1923', '1923-06' or '1923-06-15' -> (ISO date, implied precision)"""
    m = _DATE_RE.match(text or "")
    if not m:
        return None
    y, mo, d = m.group(1), m.group(2), m.group(3)
    try:
        value = date(int(y), int(mo or 1), int(d or 1)).isoformat()
    except ValueError:
        return None
    return value, ("exact" if d else "month" if mo else "year")


def effective_precision(form: dict) -> str:
    """About dates fall back to the month, as build_gramps_date does; decades and spans are years"""
    if form.get("modifier") in RANGES:
        return "year"
    precision = form.get("precision") or "exact"
    if form.get("modifier") == "about" and precision == "exact":
        return "month"
    return precision


def gramps_date(form: dict) -> dict:
    y, m, d = (int(x) for x in form["value"].split("-"))
    quality = si._QUALITIES[form.get("quality") or "regular"]
    if form.get("modifier") in RANGES:
        span = (form.get("minus") or 0, form.get("plus") or 0)
        return si.range_date(*si.year_range(form["modifier"], y, span), quality)
    precision = effective_precision(form)
    if precision == "year":
        d, m = 0, 0
    elif precision == "month":
        d = 0
    return {"_class": "Date", "dateval": [d, m, y, False],
            "modifier": si._MODIFIERS[form.get("modifier") or "regular"],
            "quality": quality, "text": ""}


def date_display(form: dict | None) -> str:
    return format_gramps_date(gramps_date(form)) if form else ""


def gramps_date_text(d: dict | None) -> str:
    """A Gramps date as Gramps Web shows it, text-only dates included"""
    if not d:
        return ""
    if d.get("modifier") == si._MODIFIERS["textonly"] or format_gramps_date(d) == "(none)":
        return (d.get("text") or "").strip()
    return format_gramps_date(d)


def date_from_gramps(d: dict | None) -> tuple[dict | None, str | None]:
    """(editor form, None) for a Gramps date the form can hold, (None, its text) for one it cannot,
    (None, None) for no date"""
    dv = list((d or {}).get("dateval") or [])
    text = gramps_date_text(d)
    if not text:
        return None, None
    modifier, quality = d.get("modifier") or 0, d.get("quality") or 0
    if (len(dv) < 4 or dv[3] or d.get("calendar") or d.get("newyear") or dv[2] <= 0
            or modifier not in (0, 1, 2, 3, 4) or quality not in _QUALITY_NAMES):
        return None, text
    form = {"quality": _QUALITY_NAMES[quality]}
    if modifier == 4:
        if len(dv) < 8 or dv[7] or any(dv[i] for i in (0, 1, 4, 5)) or not 0 <= dv[6] - dv[2] <= SPAN_MAX:
            return None, text
        start, stop = dv[2], dv[6]
        form.update({"value": f"{start:04d}-01-01", "precision": "year"})
        if start % 10 == 0 and stop == start + 9:
            form["modifier"] = "decade"
        else:
            form.update({"modifier": "span", "minus": 0, "plus": stop - start})
    else:
        day, month, year = dv[0], dv[1], dv[2]
        name = _MODIFIER_NAMES[modifier]
        if name == "about" and day:
            return None, text
        try:
            value = date(year, month or 1, day or 1).isoformat()
        except ValueError:
            return None, text
        form.update({"value": value, "modifier": name,
                     "precision": "exact" if day else "month" if month else "year"})
    form["display"] = date_display(form)
    return form, None


def date_form(asset: dict) -> dict | None:
    """The editor's date fields from an asset's date and tags; None until a date is curated"""
    exif = asset.get("exifInfo") or {}
    dt_str = asset.get("localDateTime") or exif.get("dateTimeOriginal")
    if not dt_str:
        return None
    tags = si.tag_values(asset)
    modifier, span = si.date_modifier(tags)
    if si.TAG_SYNC_DATE not in tags and not tags & DATE_TAGS and not span:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
    except ValueError:
        return None
    form = {
        "value": dt.strftime("%Y-%m-%d"),
        "precision": next((p for p, t in PRECISION_TAGS.items() if t in tags), "exact"),
        "modifier": modifier,
        "quality": next((q for q, t in QUALITY_TAGS.items() if t in tags), "regular"),
    }
    if span:
        form["minus"], form["plus"] = span
    form["precision"] = effective_precision(form)
    form["display"] = date_display(form)
    return form


def date_tags(form: dict) -> set[str]:
    tags = set()
    for table, key in ((MODIFIER_TAGS, "modifier"), (QUALITY_TAGS, "quality"),
                       (PRECISION_TAGS, "precision")):
        tag = table.get(form.get(key) or "")
        if tag:
            tags.add(tag)
    if form.get("modifier") == "span":
        tags.add(si.span_tag(form.get("minus") or 0, form.get("plus") or 0))
    return tags


def validate_link(url: str) -> str:
    url = (url or "").strip()
    if not _LINK_RE.match(url):
        raise ValueError("That is not a link starting with http:// or https://.")
    if len(url) > LINK_MAX:
        raise ValueError(f"That is too long (at most {LINK_MAX} characters).")
    return url


def validate_form(form: dict) -> dict:
    """Normalize a save body; ValueError for bad values"""
    change = form.get("change")
    out = {
        "title": (form.get("title") or "").strip(),
        "notes": (form.get("notes") or "").strip(),
        "place_gramps_id": (form.get("place_gramps_id") or "").strip() or None,
        "links": list(dict.fromkeys(validate_link(u) for u in form.get("links") or [])),
        "change": int(change) if change is not None else None,
        "gramps_id": (form.get("gramps_id") or "").strip() or None,
        "date": None,
    }
    d = form.get("date")
    if d:
        parsed = parse_date_value(d.get("value") or "")
        if not parsed:
            raise ValueError(f"unreadable date {d.get('value')!r}")
        picked = {"precision": d.get("precision") or parsed[1],
                  "modifier": d.get("modifier") or "regular",
                  "quality": d.get("quality") or "regular"}
        for key, allowed in (("precision", PRECISIONS), ("modifier", MODIFIERS),
                             ("quality", QUALITIES)):
            if picked[key] not in allowed:
                raise ValueError(f"bad {key} {picked[key]!r}")
        if picked["modifier"] in RANGES:
            picked["precision"] = "year"
        if picked["modifier"] == "span":
            for key in ("minus", "plus"):
                value = d.get(key) or 0
                if not isinstance(value, int) or not 0 <= value <= SPAN_MAX:
                    raise ValueError(f"bad {key} {value!r}")
                picked[key] = value
        out["date"] = {"value": parsed[0], **picked}
    return out


def spelled(value: str, cfg: SyncImmichConfig) -> str:
    """The spelling a missing tag is created with"""
    low = value.lower()
    if low in CANONICAL:
        return CANONICAL[low]
    if low == cfg.sync_tag.lower():
        return cfg.sync_tag
    if low == cfg.note_sync_tag.lower():
        return cfg.note_sync_tag
    return "/".join(seg[:1].upper() + seg[1:] for seg in value.split("/"))


async def apply_tags(client: ImmichClient, asset_id: str, add: dict[str, str],
                     remove: set[str]) -> None:
    """add maps lower-cased values to their spelling, remove holds lower-cased values"""
    index = {(t.get("value") or "").lower(): t for t in await client.list_tags()}
    tag_ids = []
    for low, spelling in add.items():
        tag = index.get(low) or await client.upsert_tag(spelling)
        tag_ids.append(tag["id"])
    if tag_ids:
        await client.tag_assets(tag_ids, [asset_id])
    for low in sorted(remove):
        tag = index.get(low)
        if tag:
            await client.untag_asset(tag["id"], asset_id)


def registered_gid(conn: sqlite3.Connection, asset_id: str,
                   member_ids: list[str] = ()) -> str | None:
    """The Gramps id registered for the asset or any of its stack members"""
    wanted = [asset_id, *member_ids]
    rows = conn.execute(
        "SELECT gramps_id, source_id FROM minted_media WHERE source_system='immich' "
        f"AND source_id IN ({','.join('?' * len(wanted))})", wanted).fetchall()
    for r in rows:
        if r["source_id"] == asset_id:
            return r["gramps_id"]
    return rows[0]["gramps_id"] if rows else None


def browse_accounts(accounts: list[ImmichClient], cfg: SyncImmichConfig) -> list[ImmichClient]:
    """The accounts the Photos section browses (sync.immich.photos_accounts), else all"""
    if not cfg.photos_accounts:
        return list(accounts)
    wanted = {label.lower() for label in cfg.photos_accounts}
    chosen = [c for c in accounts if (getattr(c, "label", "") or "").lower() in wanted]
    if not chosen:
        labels = ", ".join(getattr(c, "label", "") or "?" for c in accounts) or "none"
        raise SyncError(400, "sync.immich.photos_accounts names no configured Immich account "
                             f"(configured labels: {labels})")
    return chosen


def labels_for(conn: sqlite3.Connection, asset_ids: list[str]) -> dict[str, str]:
    if not asset_ids:
        return {}
    rows = conn.execute(
        f"SELECT asset_id, label FROM version_labels WHERE asset_id IN ({','.join('?' * len(asset_ids))})",
        list(asset_ids)).fetchall()
    return {r["asset_id"]: r["label"] for r in rows}


async def set_version_label(accounts: list[ImmichClient], conn: sqlite3.Connection,
                            cfg: SyncImmichConfig, asset_id: str, label: str) -> None:
    """Keep a version's note in Bifrost and mirror it into its Immich record"""
    label = (label or "").strip()
    with conn:
        if label:
            conn.execute(
                "INSERT INTO version_labels (asset_id, label, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(asset_id) DO UPDATE SET label=excluded.label, updated_at=excluded.updated_at",
                (asset_id, label, _now()))
        else:
            conn.execute("DELETE FROM version_labels WHERE asset_id=?", (asset_id,))
    asset = await si._merged_one(accounts, asset_id)
    client, _err = await si.owner_client(accounts, asset)
    record = dict((await client.get_asset_metadata(asset_id)).get(si.METADATA_KEY) or {})
    record.pop("version_label", None)
    if label:
        record["version_label"] = label
    if record:
        await client.upsert_asset_metadata(asset_id, si.METADATA_KEY, record)
    else:
        await client.delete_asset_metadata(asset_id, si.METADATA_KEY)


def _member(m: dict, primary: str | None) -> dict:
    return {"asset_id": m["id"], "filename": m.get("originalFileName") or "",
            "is_primary": m["id"] == primary, "width": m.get("width"), "height": m.get("height"),
            "size": (m.get("exifInfo") or {}).get("fileSizeInByte"),
            "date": (m.get("localDateTime") or "")[:10],
            "title": si.split_description((m.get("exifInfo") or {}).get("description") or "")[0],
            "thumb": f"/photos/api/thumb/{m['id']}"}


def managed_tags(asset: dict, cfg: SyncImmichConfig) -> dict[str, str]:
    """lower-cased value -> spelling of the tags Bifrost keeps identical across versions"""
    prefixes = ["sync/"]
    if cfg.id_tag_prefix:
        prefixes.append(cfg.id_tag_prefix.lower() + "/")
    out = {}
    for t in asset.get("tags") or []:
        value = t.get("value") or ""
        if any(value.lower().startswith(p) for p in prefixes):
            out[value.lower()] = value
    return out


def version_fields(asset: dict, cfg: SyncImmichConfig) -> dict:
    """The metadata every version of a photo should share"""
    return {"coords": si.asset_coords(asset), "tags": managed_tags(asset, cfg)}


def drift(primary: dict, member: dict) -> list[str]:
    """What differs between two version_fields results, main image first"""
    out = []
    if primary["coords"] and primary["coords"] != member["coords"]:
        out.append("location")
    missing = sorted(v for k, v in primary["tags"].items() if k not in member["tags"])
    extra = sorted(v for k, v in member["tags"].items() if k not in primary["tags"])
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if extra:
            parts.append("extra " + ", ".join(extra))
        out.append("tags (" + "; ".join(parts) + ")")
    return out


def _norm_box(face: dict) -> tuple[float, float, float, float] | None:
    w, h = face.get("imageWidth") or 0, face.get("imageHeight") or 0
    coords = [face.get("boundingBoxX1"), face.get("boundingBoxY1"),
              face.get("boundingBoxX2"), face.get("boundingBoxY2")]
    if not w or not h or any(c is None for c in coords) or coords[2] <= coords[0] or coords[3] <= coords[1]:
        return None
    return (coords[0] / w, coords[1] / h, coords[2] / w, coords[3] / h)


def _iou(a: tuple, b: tuple) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


FACE_MATCH_IOU = 0.3


async def copy_faces(client: ImmichClient, source: dict, target: dict) -> int:
    """Named faces of source appear on target: reassign the overlapping detected face or create one"""
    named = [f for f in await client.get_faces(source["id"]) if (f.get("person") or {}).get("id")]
    if not named:
        return 0
    target_faces = await client.get_faces(target["id"])
    width, height = target.get("width") or 0, target.get("height") or 0
    have = {f["person"]["id"] for f in target_faces if (f.get("person") or {}).get("id")}
    copied = 0
    for face in named:
        pid = face["person"]["id"]
        box = _norm_box(face)
        if pid in have or box is None:
            continue
        best, best_iou = None, 0.0
        for candidate in target_faces:
            if (candidate.get("person") or {}).get("id"):
                continue
            cbox = _norm_box(candidate)
            if cbox is None:
                continue
            iou = _iou(box, cbox)
            if iou > best_iou:
                best, best_iou = candidate, iou
        if best is not None and best_iou >= FACE_MATCH_IOU:
            await client.reassign_face(pid, best["id"])
            best["person"] = {"id": pid}
        elif width and height:
            x1, y1, x2, y2 = box
            await client.create_face(target["id"], pid, width, height,
                                    round(x1 * width), round(y1 * height),
                                    round((x2 - x1) * width), round((y2 - y1) * height))
        else:
            continue
        have.add(pid)
        copied += 1
    return copied


async def match_version(client: ImmichClient, cfg: SyncImmichConfig, source: dict,
                        target: dict, conn: sqlite3.Connection | None = None) -> list[str]:
    """Copy the shared metadata from source to target; returns what changed"""
    before = drift(version_fields(source, cfg), version_fields(target, cfg))
    src, dst = version_fields(source, cfg), version_fields(target, cfg)
    if src["coords"] and src["coords"] != dst["coords"]:
        await client.update_asset(target["id"], latitude=src["coords"][0], longitude=src["coords"][1])
    add = {k: v for k, v in src["tags"].items() if k not in dst["tags"]}
    remove = {k for k in dst["tags"] if k not in src["tags"]}
    await apply_tags(client, target["id"], add, remove)
    record = dict((await client.get_asset_metadata(source["id"])).get(si.METADATA_KEY) or {})
    record.pop("version_label", None)
    own_label = si.version_label(conn, target["id"]) if conn is not None else None
    if own_label:
        record["version_label"] = own_label
    if record:
        await client.upsert_asset_metadata(target["id"], si.METADATA_KEY, record)
    if await copy_faces(client, source, target):
        before.append("faces")
    return before


async def _primary_and_client(accounts: list[ImmichClient], asset_id: str) -> tuple[dict, ImmichClient]:
    asset = await si._merged_one(accounts, asset_id)
    stack = asset.get("stack") or {}
    if stack.get("primaryAssetId") and stack["primaryAssetId"] != asset_id:
        raise SyncError(400, "this asset is a stack variant, open the stack's main image")
    client, _err = await si.owner_client(accounts, asset)
    return asset, client


async def add_version(gramps: GrampsClient, accounts: list[ImmichClient], conn: sqlite3.Connection,
                      cfg: SyncImmichConfig, asset_id: str, new_id: str,
                      place_rows: dict | None = None) -> dict:
    """Stack another asset under this photo and give it the photo's tags, location and faces"""
    primary, client = await _primary_and_client(accounts, asset_id)
    if new_id == asset_id:
        raise SyncError(400, "that is this photo's main image")
    new = await si._merged_one(accounts, new_id)
    if new.get("stack"):
        raise SyncError(400, "that photo is already in a stack; remove it from that stack first")
    if new.get("ownerId") != primary.get("ownerId"):
        raise SyncError(400, "versions must belong to the same Immich account as the main image")
    _versions, member_ids = await _stack_members(client, primary)
    others = [m for m in member_ids if m != asset_id]
    main_gid = registered_gid(conn, asset_id, member_ids)
    new_gid = registered_gid(conn, new_id)
    if main_gid and new_gid and new_gid != main_gid:
        raise SyncError(400, f"both photos are already in Gramps ({main_gid} and {new_gid}); "
                             "a stack can stand for only one media object")
    if new_gid and not main_gid:
        await client.create_stack([new_id, asset_id] + others)
        photo_collections.move_items(conn, asset_id, new_id)
        main_id = new_id
    else:
        await client.create_stack([asset_id] + others + [new_id])
        main_id = asset_id
    await match_all(accounts, client, cfg, conn, main_id, [asset_id, *others, new_id])
    return await load(gramps, accounts, conn, cfg, main_id, place_rows)


async def upload_version(gramps: GrampsClient, accounts: list[ImmichClient], conn: sqlite3.Connection,
                         cfg: SyncImmichConfig, asset_id: str, filename: str, data, modified_at: str,
                         place_rows: dict | None = None) -> tuple[str, dict]:
    """Upload a file to the main image's Immich account and add it as a version"""
    _primary, client = await _primary_and_client(accounts, asset_id)
    new_id = (await client.upload_asset(filename, data, modified_at or _now()))["id"]
    await _wait_for_thumbnail(client, new_id)
    return new_id, await add_version(gramps, accounts, conn, cfg, asset_id, new_id, place_rows)


async def _wait_for_thumbnail(client: ImmichClient, asset_id: str,
                              tries: int = 120, pause: float = 0.5) -> None:
    """Immich reads an upload's metadata before it renders the thumbnail"""
    for _ in range(tries):
        if (await client.get_asset(asset_id)).get("thumbhash"):
            return
        await asyncio.sleep(pause)


async def match_member(gramps: GrampsClient, accounts: list[ImmichClient], conn: sqlite3.Connection,
                       cfg: SyncImmichConfig, asset_id: str, member_id: str,
                       place_rows: dict | None = None) -> dict:
    primary, client = await _primary_and_client(accounts, asset_id)
    _versions, member_ids = await _stack_members(client, primary)
    if member_id not in member_ids or member_id == asset_id:
        raise SyncError(404, "that asset is not a version of this photo")
    member = await si._merged_one(accounts, member_id)
    await match_version(client, cfg, primary, member, conn)
    return await load(gramps, accounts, conn, cfg, asset_id, place_rows)


async def remove_version(gramps: GrampsClient, accounts: list[ImmichClient], conn: sqlite3.Connection,
                         cfg: SyncImmichConfig, asset_id: str, member_id: str,
                         place_rows: dict | None = None) -> dict:
    """Unstack a version; its sync and ID tags go too, so no second media object gets minted"""
    primary, client = await _primary_and_client(accounts, asset_id)
    if member_id == asset_id:
        raise SyncError(400, "make another version the main image before removing this one")
    _versions, member_ids = await _stack_members(client, primary)
    if member_id not in member_ids:
        raise SyncError(404, "that asset is not a version of this photo")
    member = await si._merged_one(accounts, member_id)
    await client.remove_stack_asset(primary["stack"]["id"], member_id)
    strip = {k for k in managed_tags(member, cfg)
             if k == cfg.sync_tag.lower()
             or (cfg.id_tag_prefix and k.startswith(cfg.id_tag_prefix.lower() + "/"))}
    await apply_tags(client, member_id, {}, strip)
    return await load(gramps, accounts, conn, cfg, asset_id, place_rows)


async def clear_face_rects(gramps: GrampsClient, gramps_id: str) -> int:
    """Drop the face boxes on this media so the next sync redraws them from Immich"""
    media = await gramps.get_media_by_gramps_id(gramps_id)
    if media is None:
        return 0
    cleared = 0
    backlinks = await gramps.get_media_backlinks(media["handle"])
    for handle in backlinks.get("person") or []:
        person = await gramps.get_person(handle)
        touched = False
        for ref in person.get("media_list") or []:
            if ref.get("ref") == media["handle"] and ref.get("rect"):
                ref["rect"] = []
                touched = True
        if touched:
            await gramps.update_person(handle, person)
            cleared += 1
    return cleared


async def promote(accounts: list[ImmichClient], conn: sqlite3.Connection, cfg: SyncImmichConfig,
                  gramps: GrampsClient, asset_id: str, member_id: str, redraw_faces: bool) -> str:
    """Make a version the main image; returns the new main's id for the sync that follows"""
    primary, client = await _primary_and_client(accounts, asset_id)
    _versions, member_ids = await _stack_members(client, primary)
    if member_id not in member_ids or member_id == asset_id:
        raise SyncError(404, "that asset is not a version of this photo")
    member = await si._merged_one(accounts, member_id)
    await match_version(client, cfg, primary, member, conn)
    await client.update_stack(primary["stack"]["id"], member_id)
    photo_collections.move_items(conn, asset_id, member_id)
    gid = registered_gid(conn, asset_id, member_ids)
    if redraw_faces and gid:
        await clear_face_rects(gramps, gid)
    return member_id


async def _suggestions(client: ImmichClient, cfg: SyncImmichConfig, asset: dict,
                       member_ids: list[str], gramps_id: str | None) -> list[dict]:
    """Assets that look like versions of this photo but are not stacked with it"""
    found: dict[str, tuple[dict, str]] = {}
    skip = set(member_ids) | {asset["id"]}
    if asset.get("duplicateId"):
        try:
            for group in await client.list_duplicates():
                if group.get("duplicateId") != asset["duplicateId"]:
                    continue
                for a in group.get("assets") or []:
                    if a["id"] not in skip:
                        found[a["id"]] = (a, "Immich duplicate")
        except ImmichError:
            pass
    if gramps_id and cfg.id_tag_prefix:
        path = si.id_tag_path(cfg, gramps_id)
        try:
            tag = await client.find_tag(path)
            items = (await client.search_assets(page=1, size=50, tag_id=tag["id"]))["items"] if tag else []
        except ImmichError:
            items = []
        for a in items:
            if a["id"] not in skip:
                found.setdefault(a["id"], (a, f"tagged {path}"))
    return [{**_member(a, None), "why": why, "in_stack": bool(a.get("stack"))}
            for a, why in found.values()]


async def _stack_members(client: ImmichClient, asset: dict) -> tuple[dict | None, list[str]]:
    stack = asset.get("stack") or {}
    if not stack.get("id"):
        return None, []
    try:
        members = (await client.get_stack(stack["id"])).get("assets") or []
        error = None
    except ImmichError as exc:
        members, error = [], exc.message
    primary = stack.get("primaryAssetId")
    versions = {"stack_id": stack["id"], "primary_asset_id": primary,
                "members": [_member(m, primary) for m in members]}
    if error:
        versions["error"] = error
    return versions, [m["id"] for m in members]


def _place_info(gid: str, place_rows: dict | None, place: dict | None = None) -> dict:
    known = (place_rows or {}).get(gid)
    name = known["name"] if known else si.place_label(place) if place else gid
    return {"gramps_id": gid, "name": name, "hierarchy": known["hierarchy"] if known else [],
            "tagged": bool(known and known.get("tagged")), "known": bool(known)}


async def _gramps_side(gramps: GrampsClient, gid: str) -> tuple[dict | None, list[dict], list[dict], str | None]:
    """(media, its notes, the places whose gallery holds it, error) for a registered photo"""
    try:
        media = await gramps.get_media_by_gramps_id(gid, backlinks=True)
        if media is None:
            return None, [], [], f"the register points at {gid}, which is not in Gramps"
        backlinks = media.pop("backlinks", None) or {}
        notes = await si.media_notes(gramps, media)
        places = [await gramps.get_place(h) for h in backlinks.get("place") or []]
    except Exception as exc:  # noqa: BLE001
        return None, [], [], f"Gramps could not be read: {str(exc)[:200]}"
    return media, notes, places, None


async def load(gramps: GrampsClient, accounts: list[ImmichClient], conn: sqlite3.Connection,
               cfg: SyncImmichConfig, asset_id: str, place_rows: dict[str, dict] | None = None) -> dict:
    """The editor's record for one asset, its facts from the Gramps media object once it has one;
    a stack variant opens as its main image"""
    asset = await si._merged_one(accounts, asset_id)
    main = (asset.get("stack") or {}).get("primaryAssetId")
    if main and main != asset_id:
        asset_id, asset = main, await si._merged_one(accounts, main)
    client, _err = await si.owner_client(accounts, asset)
    tags = si.tag_values(asset)
    exif = asset.get("exifInfo") or {}
    title, link_line = si.split_description(exif.get("description") or "")
    versions, member_ids = await _stack_members(client, asset)
    for member in member_ids:
        if member != asset_id:
            photo_collections.move_items(conn, member, asset_id)
    gid = registered_gid(conn, asset_id, member_ids)
    labels = labels_for(conn, [asset_id, *member_ids])
    if versions is not None:
        details = await client.get_assets_many([m for m in member_ids if m != asset_id])
        mine = version_fields(asset, cfg)
        for member in versions["members"]:
            detail = details.get(member["asset_id"])
            if member["is_primary"]:
                member["drift"] = []
            elif detail is None:
                member["drift"] = ["unreadable"]
            else:
                member.update(_member(detail, asset_id))
                member["drift"] = drift(mine, version_fields(detail, cfg))
            member["label"] = labels.get(member["asset_id"], "")
    suggestions = await _suggestions(client, cfg, asset, member_ids, gid)
    for sg in suggestions:
        sg["gramps_id"] = registered_gid(conn, sg["asset_id"])
    media, gramps_error, change = None, None, None
    date_readonly = None
    places: list[dict] = []
    if gid:
        media, notes, holders, gramps_error = await _gramps_side(gramps, gid)
    if media is not None:
        title = media.get("desc") or ""
        date_form_, date_readonly = date_from_gramps(media.get("date"))
        notes_text = si.note_text(si.first_media_note(notes)).strip()
        links = si.media_links(media)
        places = [_place_info(h.get("gramps_id") or "", place_rows, h) for h in holders if h.get("gramps_id")]
        change = media.get("change")
    else:
        date_form_ = None if gramps_error else date_form(asset)
        notes_text, links = ("", []) if gramps_error else si.leftover_rows(conn, asset_id)
        place_gid = None if gramps_error else si.place_tag_value(asset, cfg)
        if place_gid:
            places = [_place_info(place_gid, place_rows)]
    people_links = si.person_links_map(conn)
    people = [{"id": p["id"], "name": p.get("name") or "", "linked": p["id"] in people_links}
              for p in asset.get("people") or [] if p.get("id")]
    return {
        "asset_id": asset_id,
        "filename": asset.get("originalFileName") or "",
        "mime": asset.get("originalMimeType"),
        "type": asset.get("type"),
        "width": asset.get("width"),
        "height": asset.get("height"),
        "owner": getattr(client, "label", ""),
        "owner_id": asset.get("ownerId"),
        "immich_url": f"{cfg.public_url}/photos/{asset_id}" if cfg.public_url else None,
        "thumb": f"/photos/api/thumb/{asset_id}",
        "preview": f"/photos/api/thumb/{asset_id}?size=preview",
        "title": title,
        "link_line": link_line,
        "label": labels.get(asset_id, ""),
        "date": date_form_,
        "date_readonly": date_readonly,
        "immich_date": (asset.get("localDateTime") or "")[:10],
        "place": places[0] if len(places) == 1 else None,
        "places": places,
        "tags": sorted(tags),
        "gramps": {"gramps_id": gid, "url": si.gramps_url(cfg, gid)} if gid else None,
        "gramps_error": gramps_error,
        "change": change,
        "notes": notes_text,
        "people": people,
        "versions": versions,
        "suggestions": suggestions,
        "collections": photo_collections.for_asset(conn, asset_id),
        "links": [{"url": u} for u in links],
    }


async def pending_changes(gramps: GrampsClient, accounts: list[ImmichClient],
                          conn: sqlite3.Connection, cfg: SyncImmichConfig, asset_id: str) -> list[str]:
    """What a sync would change in Gramps for a photo already there; [] when nothing"""
    asset = await si._merged_one(accounts, asset_id)
    client, _err = await si.owner_client(accounts, asset)
    _versions, member_ids = await _stack_members(client, asset) if client else (None, [])
    gid = registered_gid(conn, asset_id, member_ids)
    if not gid:
        return []
    media = await gramps.get_media_by_gramps_id(gid)
    if media is None:
        return ["media"]
    changes: set[str] = set()
    async for ev in si.update_synced(gramps, accounts, conn, cfg, gid, asset, media,
                                     False, None, si.new_counts()):
        if ev.action == "would_update":
            changes |= set((ev.data or {}).get("cols") or [ev.entity]) - {"description"}
    if client:
        async for ev in si.link_asset_faces(gramps, client, asset, asset_id, media["handle"], gid,
                                            si.person_links_map(conn), si.new_face_results(),
                                            apply=False):
            if ev.action in ("created", "updated"):
                changes.add("faces")
    return sorted(changes)


async def move_place(gramps: GrampsClient, media_handle: str, old: dict | None, new: dict | None) -> bool:
    """Take the media out of old's gallery and put it in new's; False when nothing moved"""
    if (old or {}).get("handle") == (new or {}).get("handle"):
        return False
    if old is not None:
        refs = old.get("media_list") or []
        old["media_list"] = [r for r in refs if r.get("ref") != media_handle]
        await gramps.update_place(old["handle"], old)
    if new is not None:
        await si._link_place(gramps, new, media_handle)
    return True


def _item(entity: str, action: str, asset_id: str, gid: str | None, title: str, **extra) -> SyncEvent:
    return SyncEvent(kind="item", entity=entity, action=action, source_id=asset_id,
                     gramps_id=gid, title=title, **extra)


async def save(gramps: GrampsClient, accounts: list[ImmichClient], conn: sqlite3.Connection,
               cfg: SyncImmichConfig, asset_id: str, form: dict) -> AsyncIterator[SyncEvent]:
    """Write the editor's form onto the Gramps media object, adding the photo to Gramps on its first save,
    then copy the title into Immich and finish the sync work"""
    form = validate_form(form)
    link_on = ui_settings.get_description_link(conn)
    asset = await si._merged_one(accounts, asset_id)
    stack = asset.get("stack") or {}
    if stack.get("primaryAssetId") and stack["primaryAssetId"] != asset_id:
        raise SyncError(400, "this asset is a stack variant, edit the stack's main image")
    client, _err = await si.owner_client(accounts, asset)
    _versions, member_ids = await _stack_members(client, asset)
    gid = registered_gid(conn, asset_id, member_ids)
    current_desc = ((asset.get("exifInfo") or {}).get("description") or "").strip()
    filled = any([form["title"], form["date"], form["place_gramps_id"], form["notes"], form["links"]])
    warning = None

    async def copy_title(title: str, gid: str | None) -> None:
        nonlocal warning
        wanted = compose_description(title, si.gramps_url(cfg, gid) if link_on else None)
        if wanted == current_desc:
            return
        try:
            await client.update_asset(asset_id, description=wanted)
        except ImmichError as exc:
            warning = f"Immich description not updated: {exc.message}"

    if not gid and not filled:
        await copy_title("", None)
        yield SyncEvent(kind="summary", entity="media", detail="nothing to add",
                        data={"gramps_id": None, "created": False, "changed": {}, "warning": warning})
        return

    new_place = None
    if form["place_gramps_id"]:
        try:
            new_place = await gramps.get_place_by_gramps_id(form["place_gramps_id"])
        except Exception as exc:  # noqa: BLE001
            raise SyncError(502, f"Gramps could not be read: {str(exc)[:200]}")
        if new_place is None:
            raise SyncError(400, f"{form['place_gramps_id']} names no Gramps place")

    notes = form["notes"]
    created = False
    if gid:
        media, current_notes, holders, error = await _gramps_side(gramps, gid)
        if media is None:
            raise SyncError(502 if error.startswith("Gramps could not") else 404, error)
        if form["change"] is not None and media.get("change") != form["change"]:
            raise SyncError(409, "changed in Gramps since you opened it, reload")
    else:
        async for ev in si.sync_one_asset(gramps, accounts, conn, cfg, asset_id, gramps_id=form["gramps_id"]):
            if ev.kind == "item":
                yield ev
            elif ev.kind == "summary":
                gid = ev.data["gramps_id"]
        created = True
        media, current_notes, holders, error = await _gramps_side(gramps, gid)
        if media is None:
            raise SyncError(502, error)
        extra = codes.notes_of(conn, gid) if form["gramps_id"] else ""
        if extra and extra not in notes:
            notes = f"{notes}\n\n{extra}" if notes else extra

    title = media.get("desc") or ""
    changed: dict = {}
    desc = form["title"] or asset.get("originalFileName") or gid
    if desc != title:
        media["desc"] = desc
        changed["title"] = desc
    had_form, readonly = date_from_gramps(media.get("date"))
    if form["date"]:
        new_date = gramps_date(form["date"])
        if not si.dates_equal(media.get("date"), new_date):
            media["date"] = new_date
            changed["date"] = format_gramps_date(new_date)
    elif had_form and not readonly:
        media["date"] = dict(EMPTY_DATE)
        changed["date"] = "(none)"
    if si.set_media_links(media, form["links"]):
        changed["links"] = len(form["links"])
    try:
        note_action, stale_note = await si.stage_media_note(gramps, media, notes, current_notes)
        if changed or note_action in ("created", "removed"):
            await gramps.update_media(media["handle"], media)
        if stale_note:
            await gramps.delete_note(stale_note)
    except Exception as exc:  # noqa: BLE001
        raise SyncError(502, f"Gramps update failed: {str(exc)[:200]}")
    if changed:
        yield _item("media", "updated", asset_id, gid, media["desc"], data={"cols": changed})
    if note_action:
        yield _item("note", "updated" if note_action == "removed" else note_action, asset_id, gid,
                    media["desc"], detail="note removed" if note_action == "removed" else None,
                    data={"cols": {"note": f"{len(notes)} chars"}})

    place_name = None
    if len(holders) <= 1:
        old_place = holders[0] if holders else None
        try:
            moved = await move_place(gramps, media["handle"], old_place, new_place)
        except Exception as exc:  # noqa: BLE001
            yield _item("place", "failed", asset_id, gid, media["desc"], detail=str(exc)[:200])
        else:
            if moved:
                place_name = si.place_label(new_place) if new_place else None
                yield _item("place", "updated", asset_id, (new_place or old_place).get("gramps_id"),
                            place_name or si.place_label(old_place),
                            detail="added to the gallery" if new_place else "taken out of the gallery")

    await copy_title(media["desc"], gid)
    if warning:
        yield _item("media", "skipped", asset_id, gid, media["desc"], detail=warning)

    if not created:
        async for ev in si.sync_one_asset(gramps, accounts, conn, cfg, asset_id, update=True, description=False):
            if ev.kind == "item" and ev.action != "skipped":
                yield ev
    if member_ids:
        await match_all(accounts, client, cfg, conn, asset_id, member_ids)

    yield SyncEvent(kind="summary", entity="media", gramps_id=gid, title=media["desc"],
                    detail="created" if created else "saved",
                    data={"gramps_id": gid, "created": created, "changed": changed,
                          "note": note_action, "place": place_name, "warning": warning})


async def match_all(accounts: list[ImmichClient], client: ImmichClient, cfg: SyncImmichConfig,
                    conn: sqlite3.Connection, main_id: str, member_ids: list[str]) -> int:
    """Every other version takes the main image's metadata; returns how many changed"""
    others = [m for m in member_ids if m != main_id]
    if not others:
        return 0
    main = await si._merged_one(accounts, main_id)
    details = await client.get_assets_many(others)
    changed = 0
    for member_id in others:
        detail = details.get(member_id)
        if detail is None:
            continue
        if await match_version(client, cfg, main, detail, conn):
            changed += 1
    return changed


async def _wait_for_date(client: ImmichClient, asset_id: str, value: str,
                         tries: int = 15, pause: float = 0.2) -> None:
    """Immich recomputes localDateTime in the background after a date change"""
    for _ in range(tries):
        asset = await client.get_asset(asset_id)
        if (asset.get("localDateTime") or "")[:10] == value:
            return
        await asyncio.sleep(pause)


async def _recent(client: ImmichClient, page: int, person: str) -> dict:
    try:
        return await client.search_assets(page=page, size=PAGE_SIZE, person_id=person or None,
                                          order_by="createdAt")
    except ImmichError as exc:
        if exc.status != 400:
            raise
        return await client.search_assets(page=page, size=PAGE_SIZE, person_id=person or None)


async def _stack_index(accounts: list[ImmichClient]) -> tuple[dict, dict]:
    """asset id -> (stack id, main id, size) and stack id -> member ids"""
    stacks: dict[str, tuple[str, str | None, int]] = {}
    members_of: dict[str, list[str]] = {}
    for client in accounts:
        try:
            listing = await client.list_stacks()
        except ImmichError:
            continue
        for s in listing:
            member_ids = [a["id"] for a in s.get("assets") or []]
            members_of[s["id"]] = member_ids
            for aid in member_ids:
                stacks[aid] = (s["id"], s.get("primaryAssetId"), len(member_ids))
    return stacks, members_of


async def _card_context(accounts: list[ImmichClient], conn: sqlite3.Connection):
    """Stack membership and the register, plus a card builder that uses them"""
    stacks, members_of = await _stack_index(accounts)
    minted = {r["source_id"]: r["gramps_id"] for r in conn.execute(
        "SELECT gramps_id, source_id FROM minted_media WHERE source_system='immich'")}

    def card(a: dict) -> dict:
        aid = a["id"]
        st = stacks.get(aid)
        gid = minted.get(aid)
        if not gid and st:
            gid = next((minted[m] for m in members_of.get(st[0], []) if m in minted), None)
        exif = a.get("exifInfo") or {}
        return {"asset_id": aid, "filename": a.get("originalFileName") or "",
                "title": si.split_description(exif.get("description") or "")[0],
                "type": a.get("type"),
                "thumb": f"/photos/api/thumb/{aid}", "gramps_id": gid, "owner_id": a.get("ownerId"),
                "versions": st[2] if st else 1, "is_child": bool(st and st[1] != aid),
                "missing": bool(a.get("_missing"))}

    return stacks, card


async def primaries_of(accounts: list[ImmichClient], asset_ids: list[str]) -> list[str]:
    """Stack variants swapped for their main image, order kept, duplicates dropped"""
    stacks, _members = await _stack_index(accounts)
    out = []
    for aid in asset_ids:
        st = stacks.get(aid)
        main = (st[1] or aid) if st else aid
        if main not in out:
            out.append(main)
    return out


async def fold_stacked_items(accounts: list[ImmichClient], conn: sqlite3.Connection, cid: int) -> list[str]:
    """A collection's ids after each stack variant in it gives its place to the stack's main image"""
    stacks, _members = await _stack_index(accounts)
    for aid in photo_collections.item_ids(conn, cid):
        main = stacks[aid][1] if aid in stacks else None
        if main and main != aid:
            photo_collections.move_items(conn, aid, main)
    return photo_collections.item_ids(conn, cid)


async def cards_for(accounts: list[ImmichClient], conn: sqlite3.Connection,
                    asset_ids: list[str]) -> list[dict]:
    """Cards in the given order; an asset Immich no longer has is marked missing"""
    stacks, card = await _card_context(accounts, conn)
    details = await si._merged_details(accounts, list(dict.fromkeys(asset_ids)))
    out = []
    for aid in asset_ids:
        a = details.get(aid) or {"id": aid, "originalFileName": "", "_missing": True}
        out.append(card(a))
    return out


async def search(accounts: list[ImmichClient], conn: sqlite3.Connection,
                 mode: str = "recent", q: str = "", person: str = "", page: int = 1,
                 browse: list[ImmichClient] | None = None) -> dict:
    """One page of photo cards, stack variants folded into their main image"""
    stacks, card = await _card_context(accounts, conn)
    owners: set[str] | None = None
    if browse is not None and len(browse) < len(accounts):
        owners = {await si._user_id(c) for c in browse}
    items: list[dict] = []
    next_page: int | None = None
    seen: set[str] = set()
    if mode == "synced":
        rows = conn.execute(
            "SELECT gramps_id, source_id, title FROM minted_media WHERE source_system='immich' "
            "ORDER BY minted_at DESC, gramps_id LIMIT ? OFFSET ?",
            (PAGE_SIZE + 1, (page - 1) * PAGE_SIZE)).fetchall()
        next_page = page + 1 if len(rows) > PAGE_SIZE else None
        rows = rows[:PAGE_SIZE]
        shown = [stacks[r["source_id"]][1] or r["source_id"] if r["source_id"] in stacks
                 else r["source_id"] for r in rows]
        details = await si._merged_details(accounts, list(dict.fromkeys(shown)))
        for r, aid in zip(rows, shown):
            if aid in seen:
                continue
            seen.add(aid)
            a = details.get(aid) or {"id": aid, "originalFileName": r["title"] or "", "_missing": True}
            if owners is not None and a.get("ownerId") and a["ownerId"] not in owners:
                continue
            items.append(card(a))
    else:
        for client in (browse if browse is not None else accounts):
            try:
                if q:
                    pages = [await client.search_assets(page=page, size=PAGE_SIZE, description=q,
                                                        person_id=person or None),
                             await client.search_assets(page=page, size=PAGE_SIZE, filename=q,
                                                        person_id=person or None)]
                else:
                    pages = [await _recent(client, page, person)]
            except ImmichError as exc:
                if exc.status == 400 and person:
                    continue
                raise
            for r in pages:
                for a in r["items"]:
                    if a["id"] in seen:
                        continue
                    seen.add(a["id"])
                    items.append(card(a))
                if r["nextPage"]:
                    next_page = r["nextPage"]
    return {"items": [i for i in items if not i["is_child"]], "nextPage": next_page}


async def places(gramps: GrampsClient, cfg: SyncImmichConfig) -> list[dict]:
    """Every Gramps place with its hierarchy, Place-tagged ones first"""
    rows = await gramps.list_places_full()
    by_handle = {p["handle"]: p for p in rows}

    def hierarchy(place: dict) -> list[str]:
        names, seen, cur = [], set(), place
        while cur and cur["handle"] not in seen:
            seen.add(cur["handle"])
            names.append((cur.get("name") or {}).get("value") or cur.get("gramps_id") or "")
            refs = cur.get("placeref_list") or []
            cur = by_handle.get(refs[0].get("ref")) if refs else None
        return [n for n in names if n]

    out = []
    for p in rows:
        gid = p.get("gramps_id") or ""
        if not gid:
            continue
        out.append({
            "gramps_id": gid,
            "name": (p.get("name") or {}).get("value") or gid,
            "hierarchy": hierarchy(p),
            "tagged": bool(cfg.place_tag_handle and cfg.place_tag_handle in (p.get("tag_list") or [])),
            "has_coords": bool((p.get("lat") or "").strip() and (p.get("long") or "").strip()),
        })
    out.sort(key=lambda r: (not r["tagged"], r["name"].lower()))
    return out


async def list_albums(browse: list[ImmichClient]) -> list[dict]:
    """Immich albums of the browsed accounts, by name"""
    out = []
    for client in browse:
        for a in await client.list_albums():
            out.append({"id": a["id"], "name": a.get("albumName") or "", "count": a.get("assetCount") or 0,
                        "description": a.get("description") or "", "order": a.get("order") or "desc",
                        "account": getattr(client, "label", ""),
                        "thumb": f"/photos/api/thumb/{a['albumThumbnailAssetId']}" if a.get("albumThumbnailAssetId") else None})
    out.sort(key=lambda a: (a["name"].lower(), a["account"]))
    return out


async def album_assets(browse: list[ImmichClient], album_id: str) -> tuple[dict, list[str]]:
    """The album and its asset ids in the album's own order"""
    for client in browse:
        album = next((a for a in await client.list_albums() if a["id"] == album_id), None)
        if album is None:
            continue
        ids: list[str] = []
        page: int | None = 1
        while page and len(ids) < photo_collections.MAX_ITEMS:
            r = await client.search_assets(page=page, size=200, album_id=album_id,
                                           order=album.get("order") or "desc")
            ids.extend(a["id"] for a in r["items"])
            page = r["nextPage"]
        return album, ids
    raise SyncError(404, "no such Immich album in the browsed accounts")


async def import_album(accounts: list[ImmichClient], browse: list[ImmichClient],
                       conn: sqlite3.Connection, album_id: str) -> tuple[int, int]:
    """A new collection with the album's name, description and order; returns (id, added)"""
    album, ids = await album_assets(browse, album_id)
    ids = await primaries_of(accounts, ids)
    collection = photo_collections.create(conn, album.get("albumName") or "Immich album",
                                          album.get("description") or "")
    added = photo_collections.add_items(conn, collection["id"], ids[:photo_collections.MAX_ITEMS])
    return collection["id"], added
