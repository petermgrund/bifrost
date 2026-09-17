"""Immich photos curated for Gramps"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sqlite3
from datetime import date, datetime, timezone

from ..core.clients import GrampsClient, ImmichClient
from ..core.clients.immich import ImmichError
from ..core.config import SyncImmichConfig
from . import photo_collections
from . import sync_immich as si
from .sync_immich import SyncError
from .sync_paperless import format_gramps_date

PAGE_SIZE = 24
PRECISIONS = ("exact", "month", "year")
MODIFIERS = ("regular", "about", "before", "after")
QUALITIES = ("regular", "estimated", "calculated")
MODIFIER_TAGS = {"about": si.TAG_DATE_APPROXIMATE, "before": si.TAG_DATE_BEFORE,
                 "after": si.TAG_DATE_AFTER}
QUALITY_TAGS = {"calculated": si.TAG_DATE_CALCULATED, "estimated": si.TAG_DATE_ESTIMATED}
PRECISION_TAGS = {"year": si.TAG_DATE_YEAR, "month": si.TAG_DATE_MONTH}
DATE_TAGS = set(MODIFIER_TAGS.values()) | set(QUALITY_TAGS.values()) | set(PRECISION_TAGS.values())
CANONICAL = {
    si.TAG_SYNC_DATE: "Sync/Date", si.TAG_SYNC_DESCRIPTION: "Sync/Description",
    si.TAG_SYNC_LOCATION: "Sync/Location", si.TAG_SYNC_MANUAL_FACES: "Sync/ManualFaces",
    si.TAG_DATE_APPROXIMATE: "Date/Approximate", si.TAG_DATE_BEFORE: "Date/Before",
    si.TAG_DATE_AFTER: "Date/After", si.TAG_DATE_ESTIMATED: "Date/Estimated",
    si.TAG_DATE_CALCULATED: "Date/Calculated", si.TAG_DATE_YEAR: "Date/Year",
    si.TAG_DATE_MONTH: "Date/Month",
}
_DATE_RE = re.compile(r"^\s*(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?\s*$")


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
    """About dates fall back to the month, as build_gramps_date does"""
    precision = form.get("precision") or "exact"
    if form.get("modifier") == "about" and precision == "exact":
        return "month"
    return precision


def gramps_date(form: dict) -> dict:
    y, m, d = (int(x) for x in form["value"].split("-"))
    precision = effective_precision(form)
    if precision == "year":
        d, m = 0, 0
    elif precision == "month":
        d = 0
    return {"_class": "Date", "dateval": [d, m, y, False],
            "modifier": si._MODIFIERS[form.get("modifier") or "regular"],
            "quality": si._QUALITIES[form.get("quality") or "regular"], "text": ""}


def date_display(form: dict | None) -> str:
    return format_gramps_date(gramps_date(form)) if form else ""


def date_form(asset: dict) -> dict | None:
    """The editor's date fields from an asset's date and tags"""
    exif = asset.get("exifInfo") or {}
    dt_str = asset.get("localDateTime") or exif.get("dateTimeOriginal")
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
    except ValueError:
        return None
    tags = si.tag_values(asset)
    form = {
        "value": dt.strftime("%Y-%m-%d"),
        "precision": next((p for p, t in PRECISION_TAGS.items() if t in tags), "exact"),
        "modifier": next((m for m, t in MODIFIER_TAGS.items() if t in tags), "regular"),
        "quality": next((q for q, t in QUALITY_TAGS.items() if t in tags), "regular"),
    }
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
    return tags


def validate_form(form: dict) -> dict:
    """Normalize a save body; ValueError for bad values"""
    sync = form.get("sync") or {}
    out = {
        "title": (form.get("title") or "").strip(),
        "notes": (form.get("notes") or "").strip(),
        "place_gramps_id": (form.get("place_gramps_id") or "").strip() or None,
        "sync": {k: bool(sync.get(k)) for k in ("media", "title", "date", "note")},
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


def compose_description(title: str, gramps_url: str | None) -> str:
    return f"{title}\n{gramps_url}" if gramps_url else title


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


def set_note(conn: sqlite3.Connection, asset_id: str, gramps_id: str | None, text: str) -> None:
    text = (text or "").strip()
    with conn:
        if not text:
            conn.execute("UPDATE photo_notes SET text='', updated_at=? "
                         "WHERE asset_id=? AND note_handle IS NOT NULL", (_now(), asset_id))
            conn.execute("DELETE FROM photo_notes WHERE asset_id=? AND note_handle IS NULL",
                         (asset_id,))
            return
        conn.execute(
            "INSERT INTO photo_notes (asset_id, gramps_id, text, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(asset_id) DO UPDATE SET text=excluded.text, "
            "gramps_id=COALESCE(excluded.gramps_id, photo_notes.gramps_id), "
            "updated_at=excluded.updated_at",
            (asset_id, gramps_id, text, _now()))


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
    prefixes = ["sync/", "date/"]
    for prefix in (cfg.id_tag_prefix, cfg.place_tag_prefix):
        if prefix:
            prefixes.append(prefix.lower() + "/")
    out = {}
    for t in asset.get("tags") or []:
        value = t.get("value") or ""
        if any(value.lower().startswith(p) for p in prefixes):
            out[value.lower()] = value
    return out


def version_fields(asset: dict, cfg: SyncImmichConfig) -> dict:
    """The metadata every version of a photo should share"""
    exif = asset.get("exifInfo") or {}
    return {"description": (exif.get("description") or "").strip(),
            "date": (asset.get("localDateTime") or "")[:10],
            "coords": si.asset_coords(asset),
            "tags": managed_tags(asset, cfg)}


def drift(primary: dict, member: dict) -> list[str]:
    """What differs between two version_fields results, main image first"""
    out = []
    if primary["description"] != member["description"]:
        out.append("title")
    if primary["date"] != member["date"]:
        out.append("date")
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
    fields: dict = {}
    if src["description"] != dst["description"]:
        fields["description"] = src["description"]
    if src["date"] and src["date"] != dst["date"]:
        fields["dateTimeOriginal"] = f"{src['date']}T12:00:00.000Z"
    if src["coords"] and src["coords"] != dst["coords"]:
        fields["latitude"], fields["longitude"] = src["coords"]
    if fields:
        await client.update_asset(target["id"], **fields)
        if "dateTimeOriginal" in fields:
            await _wait_for_date(client, target["id"], src["date"])
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


async def add_version(accounts: list[ImmichClient], conn: sqlite3.Connection, cfg: SyncImmichConfig,
                      asset_id: str, new_id: str, place_rows: dict | None = None) -> dict:
    """Stack another asset under this photo and give it the photo's metadata"""
    primary, client = await _primary_and_client(accounts, asset_id)
    if new_id == asset_id:
        raise SyncError(400, "that is this photo's main image")
    new = await si._merged_one(accounts, new_id)
    if new.get("stack"):
        raise SyncError(400, "that photo is already in a stack; remove it from that stack first")
    if new.get("ownerId") != primary.get("ownerId"):
        raise SyncError(400, "versions must belong to the same Immich account as the main image")
    _versions, member_ids = await _stack_members(client, primary)
    await client.create_stack([asset_id] + [m for m in member_ids if m != asset_id] + [new_id])
    await match_version(client, cfg, primary, new, conn)
    return await load(accounts, conn, cfg, asset_id, place_rows)


async def match_member(accounts: list[ImmichClient], conn: sqlite3.Connection, cfg: SyncImmichConfig,
                       asset_id: str, member_id: str, place_rows: dict | None = None) -> dict:
    primary, client = await _primary_and_client(accounts, asset_id)
    _versions, member_ids = await _stack_members(client, primary)
    if member_id not in member_ids or member_id == asset_id:
        raise SyncError(404, "that asset is not a version of this photo")
    member = await si._merged_one(accounts, member_id)
    await match_version(client, cfg, primary, member, conn)
    return await load(accounts, conn, cfg, asset_id, place_rows)


async def remove_version(accounts: list[ImmichClient], conn: sqlite3.Connection, cfg: SyncImmichConfig,
                         asset_id: str, member_id: str, place_rows: dict | None = None) -> dict:
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
    return await load(accounts, conn, cfg, asset_id, place_rows)


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
    with conn:
        conn.execute("DELETE FROM photo_notes WHERE asset_id=?", (member_id,))
        conn.execute("UPDATE photo_notes SET asset_id=?, updated_at=? WHERE asset_id=?",
                     (member_id, _now(), asset_id))
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


async def load(accounts: list[ImmichClient], conn: sqlite3.Connection, cfg: SyncImmichConfig,
               asset_id: str, place_rows: dict[str, dict] | None = None) -> dict:
    """The editor's record for one asset"""
    asset = await si._merged_one(accounts, asset_id)
    client, _err = await si.owner_client(accounts, asset)
    tags = si.tag_values(asset)
    exif = asset.get("exifInfo") or {}
    title, link_line = si.split_description(exif.get("description") or "")
    versions, member_ids = await _stack_members(client, asset)
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
    row = si.note_for(conn, asset_id, gid)
    notes = row["text"] if row else ""
    digest = hashlib.sha256(notes.strip().encode("utf-8")).hexdigest() if notes.strip() else None
    place = None
    place_gid = si.place_tag_value(asset, cfg)
    if place_gid:
        known = (place_rows or {}).get(place_gid)
        place = {"gramps_id": place_gid, "name": known["name"] if known else place_gid,
                 "hierarchy": known["hierarchy"] if known else [],
                 "tagged": bool(known and known.get("tagged")), "known": bool(known)}
    links = si.person_links_map(conn)
    people = [{"id": p["id"], "name": p.get("name") or "", "linked": p["id"] in links}
              for p in asset.get("people") or [] if p.get("id")]
    return {
        "asset_id": asset_id,
        "filename": asset.get("originalFileName") or "",
        "mime": asset.get("originalMimeType"),
        "type": asset.get("type"),
        "width": asset.get("width"),
        "height": asset.get("height"),
        "owner": getattr(client, "label", ""),
        "immich_url": f"{cfg.public_url}/photos/{asset_id}" if cfg.public_url else None,
        "thumb": f"/photos/api/thumb/{asset_id}",
        "preview": f"/photos/api/thumb/{asset_id}?size=preview",
        "title": title,
        "link_line": link_line,
        "label": labels.get(asset_id, ""),
        "date": date_form(asset),
        "place": place,
        "tags": sorted(tags),
        "sync": {"media": cfg.sync_tag.lower() in tags,
                 "title": si.TAG_SYNC_DESCRIPTION in tags,
                 "date": si.TAG_SYNC_DATE in tags,
                 "note": cfg.note_sync_tag.lower() in tags,
                 "location": si.TAG_SYNC_LOCATION in tags},
        "gramps": ({"gramps_id": gid,
                    "url": f"{cfg.gramps_public_url}/media/{gid}" if cfg.gramps_public_url else None}
                   if gid else None),
        "notes": notes,
        "note_synced": bool(row and row["note_handle"] and digest and row["synced_hash"] == digest),
        "people": people,
        "versions": versions,
        "suggestions": suggestions,
        "collections": photo_collections.for_asset(conn, asset_id),
    }


async def save(accounts: list[ImmichClient], conn: sqlite3.Connection, cfg: SyncImmichConfig,
               asset_id: str, form: dict, link_on: bool,
               place_rows: dict[str, dict] | None = None) -> dict:
    """Write the editor's form into Immich (fields, tags, metadata) and Bifrost's notes"""
    form = validate_form(form)
    asset = await si._merged_one(accounts, asset_id)
    stack = asset.get("stack") or {}
    if stack.get("primaryAssetId") and stack["primaryAssetId"] != asset_id:
        raise SyncError(400, "this asset is a stack variant, edit the stack's main image")
    client, _err = await si.owner_client(accounts, asset)
    own = si.owner_tag_values(asset)
    if own is None:
        raise SyncError(400, "cannot tell which Immich account owns this asset, so its tags cannot be edited")
    _versions, member_ids = await _stack_members(client, asset)
    gid = registered_gid(conn, asset_id, member_ids)

    wanted: dict[str, str] = {}

    def want(value: str) -> None:
        wanted[value.lower()] = spelled(value, cfg)

    if form["date"]:
        for tag in date_tags(form["date"]):
            want(tag)
        if form["sync"]["date"]:
            want(si.TAG_SYNC_DATE)
    if form["sync"]["title"] and form["title"]:
        want(si.TAG_SYNC_DESCRIPTION)
    if form["sync"]["media"]:
        want(cfg.sync_tag)
    if form["sync"]["note"] and form["notes"]:
        want(cfg.note_sync_tag)
    if form["place_gramps_id"] and cfg.place_tag_prefix:
        want(f"{cfg.place_tag_prefix}/{form['place_gramps_id']}")
    managed = set(DATE_TAGS) | {si.TAG_SYNC_DATE, si.TAG_SYNC_DESCRIPTION,
                                cfg.sync_tag.lower(), cfg.note_sync_tag.lower()}
    if cfg.place_tag_prefix:
        managed |= {t for t in own if t.startswith(cfg.place_tag_prefix.lower() + "/")}
    add = {k: v for k, v in wanted.items() if k not in own}
    remove = (own & managed) - set(wanted)

    fields: dict = {}
    gramps_url = (f"{cfg.gramps_public_url}/media/{gid}"
                  if link_on and gid and cfg.gramps_public_url else None)
    description = compose_description(form["title"], gramps_url)
    if description != ((asset.get("exifInfo") or {}).get("description") or "").strip():
        fields["description"] = description
    if form["date"] and (asset.get("localDateTime") or "")[:10] != form["date"]["value"]:
        fields["dateTimeOriginal"] = f"{form['date']['value']}T12:00:00.000Z"
    if fields:
        await client.update_asset(asset_id, **fields)
        if "dateTimeOriginal" in fields:
            await _wait_for_date(client, asset_id, form["date"]["value"])
    await apply_tags(client, asset_id, add, remove)
    set_note(conn, asset_id, gid, form["notes"])
    record = si.link_record(gid, cfg, form["notes"], si.version_label(conn, asset_id))
    if record:
        await client.upsert_asset_metadata(asset_id, si.METADATA_KEY, record)
    else:
        await client.delete_asset_metadata(asset_id, si.METADATA_KEY)
    return await load(accounts, conn, cfg, asset_id, place_rows)


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
                "date": (a.get("localDateTime") or "")[:10], "type": a.get("type"),
                "thumb": f"/photos/api/thumb/{aid}", "gramps_id": gid,
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


async def search(accounts: list[ImmichClient], conn: sqlite3.Connection, cfg: SyncImmichConfig,
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
                if mode == "tagged":
                    tag = await client.find_tag(cfg.sync_tag)
                    if tag is None:
                        continue
                    pages = [await client.search_assets(page=page, size=PAGE_SIZE, tag_id=tag["id"],
                                                        person_id=person or None)]
                elif q:
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
