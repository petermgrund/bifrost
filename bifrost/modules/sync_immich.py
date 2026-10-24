"""Immich to Gramps media sync"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import AsyncIterator

from ..core import ids
from ..core import settings as ui_settings
from ..core.clients import GrampsClient, ImmichClient
from ..core.clients.immich import ImmichError
from ..core.config import SyncImmichConfig
from ..core.db import now as _now
from ..core.events import SyncEvent, progress
from .sync_paperless import build_note_obj

METADATA_KEY = "bifrost"
NOTE_TYPE = "Media Note"
LINK_ATTR = "Source URL"
PERSON_ATTR = "Immich Person ID"
_URL_LINE_RE = re.compile(r"^https?://\S+$")


def tag_values(asset: dict) -> set[str]:
    return {t["value"].lower() for t in asset.get("tags") or [] if t.get("value")}


def asset_coords(asset: dict) -> tuple[float, float] | None:
    exif = asset.get("exifInfo") or {}
    lat, lon = exif.get("latitude"), exif.get("longitude")
    if lat is None or lon is None:
        return None
    return (round(lat, 4), round(lon, 4))


class SyncError(Exception):
    """Sync failure carrying the HTTP status the route should surface"""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


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


def person_map(people: list[dict]) -> dict[str, str]:
    """{Immich person id: Gramps person handle} from the people's Immich Person ID attributes"""
    out: dict[str, str] = {}
    for person in people:
        for a in person.get("attribute_list") or []:
            value = (a.get("value") or "").strip()
            if a.get("type") == PERSON_ATTR and value and person.get("handle"):
                out[value] = person["handle"]
    return out


async def load_person_map(gramps: GrampsClient) -> dict[str, str]:
    return person_map(await gramps.list_people(keys="handle,attribute_list"))


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
    tags = set().union(*(tag_values(c) for _, c in copies))
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


def _face_rect(face: dict) -> list:
    """Immich's pixel face box as a Gramps percent rect, padded on every side"""
    w, h = face.get("imageWidth") or 0, face.get("imageHeight") or 0
    coords = [face.get("boundingBoxX1"), face.get("boundingBoxY1"),
              face.get("boundingBoxX2"), face.get("boundingBoxY2")]
    if not w or not h or any(c is None for c in coords):
        return []
    x1, y1, x2, y2 = coords
    if x2 <= x1 or y2 <= y1:
        return []
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
    person_map: dict[str, str],
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

    linked_people: dict[str, tuple[str, list]] = {}
    for face in faces:
        person = face.get("person") or {}
        pid = person.get("id")
        if not pid:
            continue
        handle = person_map.get(pid)
        if handle:
            label = person.get("name") or pid
            prev = linked_people.get(handle)
            if prev is None or not prev[1]:
                linked_people[handle] = (label, _face_rect(face))
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
    description: bool = True,
    person_map: dict[str, str] | None = None,
    live_ids: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """Create the Gramps media for one Immich asset, titled by its file name; re-runs finish links idempotently"""
    yield SyncEvent(kind="started", detail=f"immich asset {asset_id}")

    asset = await _merged_one(accounts, asset_id)
    if asset.get("isTrashed"):
        raise SyncError(400, "asset is in the Immich trash")
    stack = asset.get("stack") or {}
    if stack.get("primaryAssetId") and stack["primaryAssetId"] != asset_id:
        raise SyncError(400, "this asset is a stack variant. sync the stack's main image instead")

    row = conn.execute(
        "SELECT gramps_id FROM minted_media WHERE source_system='immich' AND source_id=? "
        "AND withdrawn_at IS NULL", (asset_id,),
    ).fetchone()
    if row is None and stack.get("primaryAssetId"):
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
                "SELECT gramps_id FROM minted_media WHERE source_system='immich' AND withdrawn_at IS NULL "
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
                                          True, None, counts, description):
                if ev.kind == "item" and ev.entity == "media" and ev.action == "updated":
                    updated_cols.update((ev.data or {}).get("cols") or {})
                yield ev
            title = existing.get("desc") or title
            gramps_path = existing.get("path") or gramps_path
    else:
        if live_ids is None:
            live_ids = await gramps.list_media_gramps_ids()
        if gramps_id:
            gid = gramps_id.strip().upper()
            if not ids.MANUAL_ID_RE.match(gid):
                raise SyncError(400, f"invalid gramps_id {gramps_id!r} (6 chars, safe alphabet)")
            if why := ids.guard_reason(gid):
                raise SyncError(400, f"gramps_id {gid} {why}, so it is never issued")
            if gid in live_ids:
                raise SyncError(400, f"gramps_id {gid} already exists in Gramps")
            if gid in ids.all_ids_ever_seen(conn, open_reservations=False):
                raise SyncError(400, f"gramps_id {gid} was issued before and can't be reused")
        else:
            gid = ids.generate_gramps_id(ids.all_ids_ever_seen(conn, live_ids))

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

        try:
            await gramps.create_media(media_obj)
        except Exception as exc:
            raise SyncError(502, f"Gramps create failed: {exc}")
        with conn:
            try:
                ids.register_minted(conn, gid, "immich", asset_id, _now())
            except ids.IdReused as exc:
                raise SyncError(409, f"media {gid} created in Gramps but not registered: {exc}")
        created = True
        yield SyncEvent(
            kind="item", entity="media", action="created", source_id=asset_id,
            gramps_id=gid, title=title, detail=gramps_path,
        )
        try:
            await gramps.store_checksum(media_obj)
        except Exception as exc:
            counts["errors"] += 1
            yield SyncEvent(
                kind="item", entity="media", action="failed", source_id=asset_id,
                gramps_id=gid, title=title,
                detail=f"created, but Gramps could not read its file for the checksum: {str(exc)[:200]}")

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
            record_error = await write_link_record(accounts, asset, gid, cfg)
            if record_error:
                yield SyncEvent(
                    kind="item", entity="tag", action="failed", source_id=asset_id,
                    gramps_id=gid, title=title, detail=record_error)

    if person_map is None:
        person_map = await load_person_map(gramps)
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

    note_synced = None
    if not refreshed:
        try:
            async for ev in adopt_rows(gramps, conn, asset_id, media_obj):
                if ev.entity == "note":
                    note_synced = ev.action
                yield ev
        except Exception as exc:
            yield SyncEvent(kind="item", entity="note", action="failed", source_id=asset_id,
                            gramps_id=gid, title=title, detail=str(exc)[:200])

    yield SyncEvent(
        kind="summary", entity="media", gramps_id=gid, title=title,
        detail="created" if created else "already synced",
        data={
            "gramps_id": gid,
            "created": created,
            "title": title,
            "path": gramps_path,
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


def new_counts() -> dict:
    return {"created": 0, "descriptions_updated": 0,
            "versions_updated": 0, "links_updated": 0,
            "id_tags_written": 0, "notes_synced": 0, "skipped": 0, "errors": 0}


def split_description(text: str) -> tuple[str, str | None]:
    """(title, trailing URL line or None)"""
    lines = [line.strip() for line in (text or "").strip().splitlines()]
    if len(lines) >= 2 and _URL_LINE_RE.match(lines[-1]):
        return "\n".join(lines[:-1]).strip(), lines[-1]
    return "\n".join(lines).strip(), None


def compose_description(title: str, gramps_url: str | None) -> str:
    return f"{title}\n{gramps_url}" if gramps_url else title


def is_url_line(text: str) -> bool:
    return bool(_URL_LINE_RE.match((text or "").strip()))


def gramps_url(cfg: SyncImmichConfig, gramps_id: str | None) -> str | None:
    return f"{cfg.gramps_public_url}/media/{gramps_id}" if gramps_id and cfg.gramps_public_url else None


def wanted_description(media: dict, cfg: SyncImmichConfig, link_on: bool) -> str:
    """The Immich description that mirrors a media object: its title, plus the Gramps link when that is on"""
    return compose_description(media.get("desc") or "", gramps_url(cfg, media.get("gramps_id")) if link_on else None)


def wanted_title(asset: dict) -> str:
    return asset.get("originalFileName") or ""


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


def link_record(gramps_id: str | None, cfg: SyncImmichConfig,
                version_label: str | None = None) -> dict:
    """The bifrost metadata record an asset carries in Immich"""
    rec: dict = {}
    if gramps_id:
        rec["gramps_id"] = gramps_id
        if cfg.gramps_public_url:
            rec["gramps_url"] = gramps_url(cfg, gramps_id)
    if (version_label or "").strip():
        rec["version_label"] = version_label.strip()
    return rec


async def write_link_record(
    accounts: list[ImmichClient], asset: dict, gramps_id: str, cfg: SyncImmichConfig,
) -> str | None:
    """Write the asset's bifrost record, keeping the version label it already carries"""
    client, _probe_error = await owner_client(accounts, asset)
    try:
        current = (await client.get_asset_metadata(asset["id"])).get(METADATA_KEY) or {}
        await client.upsert_asset_metadata(
            asset["id"], METADATA_KEY, link_record(gramps_id, cfg, current.get("version_label")))
    except ImmichError as exc:
        return f"link record write failed: {exc.message}"
    return None


async def media_notes(gramps: GrampsClient, media: dict) -> list[dict]:
    """The notes on a media object, in its order"""
    found = []
    for handle in media.get("note_list") or []:
        note = await gramps.get_note(handle)
        if note is not None:
            found.append(note)
    return found


def first_media_note(notes: list[dict]) -> dict | None:
    return next((n for n in notes if n.get("type") == NOTE_TYPE), None)


def note_text(note: dict | None) -> str:
    return ((note or {}).get("text") or {}).get("string") or ""


async def stage_media_note(gramps: GrampsClient, media: dict, text: str,
                           notes: list[dict] | None = None) -> tuple[str | None, str | None]:
    """Make the first Media Note read text (empty removes it) without saving the media;
    (what happened, handle of a note to delete once the media is saved)"""
    text = (text or "").strip()
    current = first_media_note(await media_notes(gramps, media) if notes is None else notes)
    if current is None:
        if not text:
            return None, None
        handle = ids.generate_handle()
        items = await gramps._paged("/notes/", keys="gramps_id")
        nid = ids.next_sequential_id("N", {i["gramps_id"] for i in items if i.get("gramps_id")})
        await gramps.create_note(build_note_obj(handle, nid, text, NOTE_TYPE))
        media.setdefault("note_list", []).append(handle)
        return "created", None
    if not text:
        media["note_list"] = [h for h in media.get("note_list") or [] if h != current["handle"]]
        return "removed", current["handle"]
    if note_text(current).strip() == text:
        return None, None
    await gramps.update_note(current["handle"],
                             build_note_obj(current["handle"], current["gramps_id"], text, NOTE_TYPE))
    return "updated", None


async def write_media_note(gramps: GrampsClient, media: dict, text: str) -> str | None:
    """Make the first Media Note read text and save the media when its notes changed"""
    action, stale = await stage_media_note(gramps, media, text)
    if action in ("created", "removed"):
        await gramps.update_media(media["handle"], media)
    if stale:
        await gramps.delete_note(stale)
    return action


async def append_media_note(gramps: GrampsClient, media: dict, text: str) -> str | None:
    """Add text to the first Media Note unless it is already in it"""
    text = (text or "").strip()
    if not text:
        return None
    current = note_text(first_media_note(await media_notes(gramps, media))).strip()
    if text in current:
        return None
    return await write_media_note(gramps, media, f"{current}\n\n{text}" if current else text)


def media_links(media: dict) -> list[str]:
    return [a.get("value") or "" for a in media.get("attribute_list") or []
            if a.get("type") == LINK_ATTR and a.get("value")]


def set_media_links(media: dict, urls: list[str]) -> bool:
    """Replace the Source URL attributes with urls, other attributes kept; True when they changed"""
    if media_links(media) == list(urls):
        return False
    kept = [a for a in media.get("attribute_list") or [] if a.get("type") != LINK_ATTR]
    media["attribute_list"] = kept + [_attr(LINK_ATTR, url) for url in urls]
    return True


def leftover_rows(conn: sqlite3.Connection, asset_id: str) -> tuple[str, list[str]]:
    """The note and links Bifrost's own tables still hold for a photo not in Gramps"""
    row = conn.execute("SELECT text FROM photo_notes WHERE asset_id=?", (asset_id,)).fetchone()
    links = [r["url"] for r in conn.execute(
        "SELECT url FROM photo_links WHERE asset_id=? ORDER BY id", (asset_id,))]
    return (row["text"] if row else "").strip(), links


def delete_leftover_rows(conn: sqlite3.Connection, asset_id: str) -> None:
    with conn:
        conn.execute("DELETE FROM photo_notes WHERE asset_id=?", (asset_id,))
        conn.execute("DELETE FROM photo_links WHERE asset_id=?", (asset_id,))


async def adopt_rows(gramps: GrampsClient, conn: sqlite3.Connection, asset_id: str,
                     media: dict) -> AsyncIterator[SyncEvent]:
    """A created media takes the note and links Bifrost kept for the photo, and the rows go"""
    text, links = leftover_rows(conn, asset_id)
    gid = media.get("gramps_id")
    if text:
        if is_url_line(text):
            links = links + [text] if text not in links else links
        else:
            action = await append_media_note(gramps, media, text)
            if action:
                yield SyncEvent(kind="item", entity="note", action=action, source_id=asset_id,
                                gramps_id=gid, title=media.get("desc"),
                                data={"cols": {"note": f"{len(text)} chars"}})
    if links:
        wanted = list(dict.fromkeys(media_links(media) + links))
        if set_media_links(media, wanted):
            await gramps.update_media(media["handle"], media)
            yield SyncEvent(kind="item", entity="media", action="updated", source_id=asset_id,
                            gramps_id=gid, title=media.get("desc"),
                            data={"cols": {"links": f"{len(links)} added"}})
    delete_leftover_rows(conn, asset_id)


def place_label(place: dict) -> str:
    return (place.get("name") or {}).get("value") or place.get("gramps_id") or "?"


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
    if asset.get("originalPath"):
        gramps_path, _mime = gramps_file(asset, cfg, preview)
        if gramps_path != (media.get("path") or ""):
            cols["file"] = f"{media.get('path') or '(none)'} → {gramps_path}"
    if not media.get("checksum"):
        cols["checksum"] = "missing"
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
    apply: bool,
    selected: set[str] | None,
    counts: dict,
    description: bool = True,
) -> AsyncIterator[SyncEvent]:
    """Bring one registered media object's file, links and ID tag up to date with its Immich asset,
    and the asset's description up to date with the media's title"""
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
    wanted = wanted_description(media, cfg, ui_settings.get_description_link(conn))
    current = ((asset.get("exifInfo") or {}).get("description") or "").strip()
    desc_cols = {"description": f"{current!r} → {wanted!r}"} if description and wanted != current else {}
    pending = {**cols, **tag_cols, **desc_cols}

    if not pending:
        counts["skipped"] += 1
        return
    if not apply:
        yield SyncEvent(kind="item", entity="media", action="would_update",
                        source_id=asset_id, gramps_id=gid,
                        title=media.get("desc"), data={"cols": pending})
        return

    if selected is not None and f"media:{asset_id}" not in selected:
        return
    landed = dict(cols)
    if "checksum" in cols and "file" not in cols:
        try:
            media["checksum"] = await gramps.media_md5(media["handle"])
        except Exception as exc:
            counts["errors"] += 1
            del landed["checksum"]
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, gramps_id=gid, title=media.get("desc"),
                            detail=f"Gramps could not read the file for its checksum: {str(exc)[:200]}")
    if landed:
        if "file" in cols:
            media["path"], media["mime"] = gramps_file(asset, cfg, preview)
            media["checksum"] = ""
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
            try:
                await gramps.store_checksum(media)
            except Exception as exc:
                counts["errors"] += 1
                landed.pop("checksum", None)
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, gramps_id=gid, title=media.get("desc"),
                                detail=f"Gramps could not read the new file for its checksum: {str(exc)[:200]}")
        elif "link" in cols:
            counts["links_updated"] += 1
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
            record_error = await write_link_record(accounts, asset, gid, cfg)
            if record_error:
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="tag", action="failed",
                                source_id=asset_id, gramps_id=gid,
                                title=media.get("desc"), detail=record_error)
    if desc_cols:
        client, _probe_error = await owner_client(accounts, asset)
        try:
            await client.update_asset(asset_id, description=wanted)
            counts["descriptions_updated"] += 1
            landed.update(desc_cols)
        except ImmichError as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, gramps_id=gid, title=media.get("desc"),
                            detail=f"Immich description not updated: {exc.message}")
    if landed:
        yield SyncEvent(kind="item", entity="media", action="updated",
                        source_id=asset_id, gramps_id=gid,
                        title=media["desc"], data={"cols": landed})


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
        "SELECT gramps_id, source_id FROM minted_media WHERE source_system='immich' AND withdrawn_at IS NULL"
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
        return progress(label, done, total)

    detail_by_id: dict[str, dict | None] = {}
    for start in range(0, len(detail_ids), _DETAIL_BATCH):
        yield _progress("Reading photo details")
        batch = detail_ids[start:start + _DETAIL_BATCH]
        detail_by_id.update(await _merged_details(accounts, batch))
        done += len(batch)

    people: dict[str, str] | None = None
    live_ids: set[str] | None = None
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
        if not apply:
            yield SyncEvent(kind="item", entity="media", action="would_create",
                            source_id=asset_id, title=title, data={"cols": {"title": title}})
            continue
        if selected is not None and f"media:{asset_id}" not in selected:
            continue
        if people is None:
            people = await load_person_map(gramps)
        if live_ids is None:
            live_ids = await gramps.list_media_gramps_ids()
        try:
            async for ev in sync_one_asset(gramps, accounts, conn, cfg, asset_id,
                                           person_map=people, live_ids=live_ids):
                if ev.kind == "item":
                    if ev.action == "failed":
                        counts["errors"] += 1
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
                                      apply, selected, counts):
            yield ev

    if total:
        yield _progress(update_label if update_targets else create_label)
    yield SyncEvent(kind="summary", data=counts)
