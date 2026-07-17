"""Immich → Gramps media sync.

Two entry points: sync_one_asset (initial sync of one asset, kept for the
/sync/immich/asset endpoint) and sync_assets (the Sync section's scan —
preview/apply over the Photos album whitelist, mirroring sync_paperless's
shape). Reduced re-add (2026-07-14) of the integration removed in 77cf402;
differences from the old tag-driven design:

- Faces become plain person↔media associations (MediaRef with rect: []) —
  no bounding boxes, no face_pads.
- The Gramps date comes ONLY from the asset's gda.date KV entry (a
  Gramps-model date maintained by the Photos editor, shape in core/gda).
  No gda.date → no date on the media object. Never Immich's timestamp.
- The media title comes from the gda.gramps KV entry's "title", falling back
  to the original filename.
- After a successful sync, gda.gramps gets gramps_id/synced_at written back
  so the Photos page can show sync state. A re-run for an already-synced asset finishes
  that tail idempotently (KV write-back, missing person links) instead of
  failing.

Person links are read fresh from the face-linker's person_map.yaml on every
call — that file is owned by the face-linker GUI (:8767), the only face tool.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import yaml

from ..core import ids
from ..core.clients import GrampsClient, ImmichClient
from ..core.clients.immich import ImmichError
from ..core.config import SyncImmichConfig
from ..core.events import SyncEvent
from .sync_paperless import format_gramps_date

_MODIFIERS = {"regular": 0, "before": 1, "after": 2, "about": 3, "range": 4, "span": 5, "textonly": 6}
_QUALITIES = {"regular": 0, "estimated": 1, "calculated": 2}


class SyncError(Exception):
    """Sync failure carrying the HTTP status the route should surface."""

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
        f"originalPath {original_path!r} is under no configured path mapping — "
        "add it to sync.immich.path_mappings (and mount it in grampsweb) first",
    )


def gda_date_to_gramps(gd: dict) -> dict:
    """Map urd's gda.date value (string modifier/quality, Gramps-style parts)
    to the Gramps API Date object (integer codes, dateval array)."""
    modifier = _MODIFIERS.get(gd.get("modifier") or "regular")
    quality = _QUALITIES.get(gd.get("quality") or "regular")
    if modifier is None or quality is None:
        raise SyncError(
            400, f"gda.date has unknown modifier/quality: {gd.get('modifier')!r}/{gd.get('quality')!r}"
        )

    def part(p: dict | None) -> list:
        p = p or {}
        return [int(p.get("day") or 0), int(p.get("month") or 0), int(p.get("year") or 0), False]

    if modifier == _MODIFIERS["textonly"]:
        dateval = [0, 0, 0, False]
    elif modifier in (_MODIFIERS["range"], _MODIFIERS["span"]):
        dateval = part(gd.get("start")) + part(gd.get("stop"))
    else:
        dateval = part(gd.get("start"))
    return {
        "_class": "Date",
        "dateval": dateval,
        "modifier": modifier,
        "quality": quality,
        "text": gd.get("text") or "",
    }


def load_person_map(path: Path | None) -> dict[str, dict]:
    """{immich_person_id: {"handle": ..., "label": ...}} from person_map.yaml."""
    if path is None or not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    return {
        e["immich_person_id"]: {"handle": e["gramps_handle"], "label": e.get("label") or ""}
        for e in (raw.get("people") or [])
        if e.get("immich_person_id") and e.get("gramps_handle")
    }


def _attr(attr_type: str, value: str) -> dict:
    return {
        "_class": "Attribute",
        "type": attr_type,
        "value": value,
        "private": False,
        "citation_list": [],
        "note_list": [],
    }


def _media_ref(media_handle: str) -> dict:
    # rect: [] is the proven no-region shape (the old place-link code used it).
    return {
        "_class": "MediaRef",
        "ref": media_handle,
        "rect": [],
        "attribute_list": [],
        "citation_list": [],
        "note_list": [],
        "private": False,
    }


async def sync_one_asset(
    gramps: GrampsClient,
    immich: ImmichClient,
    conn: sqlite3.Connection,
    cfg: SyncImmichConfig,
    asset_id: str,
    gramps_id: str | None = None,
) -> AsyncIterator[SyncEvent]:
    """Create the Gramps media object for one Immich asset (initial sync).

    Yields SyncEvents for the runs ledger; the summary event's `data` is the
    route's response payload. Raises SyncError for the route to map to HTTP.
    Re-running for an already-synced asset completes the idempotent tail
    (person links, KV write-back) and reports created=False.
    """
    yield SyncEvent(kind="started", detail=f"immich asset {asset_id}")

    try:
        asset = await immich.get_asset(asset_id)
    except ImmichError as exc:
        status = 404 if exc.status in (400, 404) else 502
        raise SyncError(status, f"asset lookup failed: {exc.message}")
    if asset.get("isTrashed"):
        raise SyncError(400, "asset is in the Immich trash")
    stack = asset.get("stack") or {}
    if stack.get("primaryAssetId") and stack["primaryAssetId"] != asset_id:
        raise SyncError(400, "this asset is a stack variant — sync the stack's main image instead")

    try:
        kv = await immich.get_metadata(asset_id)
    except ImmichError as exc:
        raise SyncError(502, f"could not read asset metadata: {exc.message}")
    if is_verso(kv, cfg):
        raise SyncError(
            400, "this asset is a verso — it has no metadata of its own and syncs with its recto")
    gk = dict(kv.get(cfg.gramps_key) or {})
    gd = kv.get(cfg.date_key)

    # --- duplicate / resume detection -------------------------------------
    existing = None
    if gk.get("gramps_id"):
        existing = await gramps.get_media_by_gramps_id(gk["gramps_id"])
    if existing is None:
        row = conn.execute(
            "SELECT gramps_id FROM minted_media WHERE source_system='immich' AND source_id=?",
            (asset_id,),
        ).fetchone()
        if row:
            existing = await gramps.get_media_by_gramps_id(row[0])

    if existing is not None:
        gid = existing["gramps_id"]
        media_handle = existing["handle"]
        title = existing.get("desc") or ""
        gramps_path = existing.get("path") or ""
        created = False
        yield SyncEvent(
            kind="item", entity="media", action="skipped", source_id=asset_id,
            gramps_id=gid, title=title, detail="already in Gramps — finishing links/KV",
        )
    else:
        # --- resolve the Gramps ID ----------------------------------------
        live_ids = await gramps.list_media_gramps_ids()
        if gramps_id:
            gid = gramps_id.strip().upper()
            if not ids.MANUAL_ID_RE.match(gid):
                raise SyncError(400, f"invalid gramps_id {gramps_id!r} (6 chars, safe alphabet)")
            if gid in live_ids:
                raise SyncError(400, f"gramps_id {gid} already exists in Gramps")
        else:
            gid = ids.generate_gramps_id(live_ids | ids.unminted_reserved(conn))

        gramps_path = translate_path(asset["originalPath"], cfg.path_mappings)
        title = (gk.get("title") or "").strip() or asset.get("originalFileName") or gid
        media_handle = ids.generate_handle()

        media_obj = {
            "_class": "Media",
            "handle": media_handle,
            "gramps_id": gid,
            "desc": title,
            "path": gramps_path,
            "mime": asset.get("originalMimeType") or "image/jpeg",
            "private": False,
            "change": int(datetime.now(timezone.utc).timestamp()),
            "attribute_list": [_attr("Immich ID", asset_id)]
            + ([_attr("Immich URL", f"{cfg.public_url}/photos/{asset_id}")] if cfg.public_url else []),
        }
        if gd:
            media_obj["date"] = gda_date_to_gramps(gd)

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

    # --- person associations (plain, rect-less) ----------------------------
    person_map = load_person_map(cfg.person_map_path)
    people_linked: list[str] = []
    people_unmatched: list[str] = []
    people_failed: list[dict] = []
    try:
        faces = await immich.get_faces(asset_id)
    except ImmichError as exc:
        faces = []
        yield SyncEvent(
            kind="item", entity="face", action="failed", source_id=asset_id,
            detail=f"face lookup failed: {exc.message}",
        )

    linked_people: dict[str, str] = {}  # gramps handle -> display label
    for face in faces:
        person = face.get("person") or {}
        pid = person.get("id")
        if not pid:
            continue
        entry = person_map.get(pid)
        if entry:
            linked_people[entry["handle"]] = entry["label"] or person.get("name") or pid
        else:
            name = person.get("name") or pid
            if name not in people_unmatched:
                people_unmatched.append(name)

    for handle, label in linked_people.items():
        try:
            person = await gramps.get_person(handle)
            refs = person.setdefault("media_list", [])
            if any(r.get("ref") == media_handle for r in refs):
                people_linked.append(label)
                continue
            refs.append(_media_ref(media_handle))
            await gramps.update_person(handle, person)
            people_linked.append(label)
            yield SyncEvent(
                kind="item", entity="face", action="created", source_id=asset_id,
                gramps_id=gid, title=label, detail="person↔media association",
            )
        except Exception as exc:  # best-effort per person; never roll back the media
            people_failed.append({"person": label, "error": str(exc)[:200]})
            yield SyncEvent(
                kind="item", entity="face", action="failed", source_id=asset_id,
                gramps_id=gid, title=label, detail=str(exc)[:200],
            )

    # --- KV write-back (merge, don't clobber) -------------------------------
    warning = None
    gk["schema"] = 1
    gk["gramps_id"] = gid
    if created or not gk.get("synced_at"):
        gk["synced_at"] = _now()
    try:
        await immich.put_metadata(asset_id, cfg.gramps_key, gk)
    except ImmichError as exc:
        warning = (
            f"KV write-back failed: {exc.message} — media exists as {gid}; "
            "re-run the sync to finish"
        )

    yield SyncEvent(
        kind="summary", entity="media", gramps_id=gid, title=title,
        detail="created" if created else "already synced — links/KV refreshed",
        data={
            "gramps_id": gid,
            "created": created,
            "title": title,
            "path": gramps_path,
            "date": (gd or {}).get("display"),
            "people_linked": people_linked,
            "people_unmatched": people_unmatched,
            "people_failed": people_failed,
            "warning": warning,
        },
    )


# --- Sync-section scan: preview/apply over the album whitelist -----------------

_ALBUM_ASSET_CAP = 5000  # per album (and total when unscoped), safety valve
_KV_BATCH = 40


def wanted_title(kv: dict, asset: dict, cfg: SyncImmichConfig) -> str:
    """The title a synced media object should carry — gda.gramps title,
    falling back to the filename (same rule sync_one_asset applies)."""
    gk = kv.get(cfg.gramps_key) or {}
    return (gk.get("title") or "").strip() or asset.get("originalFileName") or ""


def dates_equal(gramps_date: dict | None, new_date: dict | None) -> bool:
    """Compare only the fields bifrost writes — the API decorates stored
    dates with sortval/calendar/etc. that a fresh gda translation lacks."""
    a, b = gramps_date or {}, new_date or {}
    return (
        (a.get("dateval") or []) == (b.get("dateval") or [])
        and (a.get("modifier") or 0) == (b.get("modifier") or 0)
        and (a.get("quality") or 0) == (b.get("quality") or 0)
        and (a.get("text") or "") == (b.get("text") or "")
    )


def update_plan(kv: dict, asset: dict, media: dict, cfg: SyncImmichConfig) -> dict:
    """cols dict of pending changes for an already-synced asset ({} = in
    sync). A Gramps-side date is never cleared: no gda.date → hands off.
    A "file" col means the Gramps media no longer points at this asset's
    file — the stack's main changed — and needs repointing (the photo
    analog of the Paperless selected-version repoint)."""
    cols: dict = {}
    title = wanted_title(kv, asset, cfg)
    if title and title != (media.get("desc") or ""):
        cols["title"] = f"{media.get('desc')!r} → {title!r}"
    gd = kv.get(cfg.date_key)
    if gd and not dates_equal(media.get("date"), gda_date_to_gramps(gd)):
        cols["date"] = f"{format_gramps_date(media.get('date'))} → {gd.get('display') or '?'}"
    if asset.get("originalPath"):
        gramps_path = translate_path(asset["originalPath"], cfg.path_mappings)
        if gramps_path != (media.get("path") or ""):
            cols["file"] = f"{media.get('path') or '(none)'} → {gramps_path}"
    return cols


def _set_attr(media: dict, attr_type: str, value: str) -> None:
    """Update (or add) a media attribute by type — used when repointing a
    media object at a new main image's file."""
    for att in media.setdefault("attribute_list", []):
        if att.get("type") == attr_type:
            att["value"] = value
            return
    media["attribute_list"].append(_attr(attr_type, value))


def is_verso(kv: dict, cfg: SyncImmichConfig) -> bool:
    """Versos carry no metadata of their own and never sync — they are the
    back of their recto (gda.verso: {"recto": <asset id>})."""
    return bool((kv.get(cfg.verso_key) or {}).get("recto"))


async def _scan_scope(immich: ImmichClient, album_ids: list[str]) -> tuple[list[dict], bool]:
    """All assets in the whitelisted albums (every album when unscoped),
    deduped. Returns (assets, capped)."""
    capped = False

    async def one_scope(album_id: str | None) -> list[dict]:
        nonlocal capped
        items: list[dict] = []
        page: int | None = 1
        while page and len(items) < _ALBUM_ASSET_CAP:
            r = await immich.search_assets(page=page, size=200, album_id=album_id)
            items.extend(r["items"])
            page = r["nextPage"]
        if page:
            capped = True
        return items

    seen: set[str] = set()
    assets: list[dict] = []
    for scope in album_ids or [None]:
        for a in await one_scope(scope):
            if a["id"] not in seen:
                seen.add(a["id"])
                assets.append(a)
    return assets, capped


async def sync_assets(
    gramps: GrampsClient,
    immich: ImmichClient,
    conn: sqlite3.Connection,
    cfg: SyncImmichConfig,
    album_ids: list[str],
    apply: bool = False,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """Scan the Photos scope and create/update Gramps media objects.

    - A titled, unsynced asset (gda.gramps.title set) is a CREATE candidate —
      the title is the deliberate "I want this in Gramps" signal.
    - A synced asset whose gda title/date drifted from Gramps is an UPDATE
      candidate; the row's cols say which fields.
    - Versos and untitled unsynced assets are not candidates.
    - `selected` ("media:<asset_id>" keys) filters what apply touches;
      preview always shows the full picture.
    """
    counts = {"created": 0, "titles_updated": 0, "dates_updated": 0,
              "versions_updated": 0, "kv_healed": 0, "skipped": 0, "errors": 0}

    assets, capped = await _scan_scope(immich, album_ids)
    # Stack children never sync — the main image carries the metadata. The
    # /stacks listing is the only complete membership source (search results
    # report stack: null on v3.0.1); without it we might create media for a
    # variant, so a failure here aborts the scan rather than guessing.
    try:
        stack_children = {
            a["id"]
            for s in await immich.list_stacks()
            for a in (s.get("assets") or [])
            if a["id"] != s.get("primaryAssetId")
        }
    except ImmichError as exc:
        raise SyncError(502, f"could not list Immich stacks: {exc.message}")
    scope = f"{len(assets)} asset(s) in {len(album_ids) or 'all'} album(s)"
    if capped:
        scope += f" — CAPPED at {_ALBUM_ASSET_CAP}/album, results are incomplete"
    yield SyncEvent(kind="started", detail=scope)

    # KV metadata is not searchable server-side (invariant) — brute-force
    # reads over the scope, batched for progress reporting.
    kv_by_id: dict[str, dict | None] = {}
    for start in range(0, len(assets), _KV_BATCH):
        yield SyncEvent(kind="progress", detail="Reading photo metadata",
                        data={"done": start, "total": len(assets),
                              "percent": round(100 * start / max(len(assets), 1))})
        batch = assets[start:start + _KV_BATCH]
        kv_by_id.update(await immich.get_metadata_many([a["id"] for a in batch]))

    for asset in assets:
        asset_id = asset["id"]
        if asset_id in stack_children:
            continue
        kv = kv_by_id.get(asset_id)
        if kv is None:  # FAILED fetch — never treat as "no metadata"
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, title=asset.get("originalFileName"),
                            detail="KV metadata fetch failed")
            continue
        if is_verso(kv, cfg):
            continue

        gk = kv.get(cfg.gramps_key) or {}
        gid = gk.get("gramps_id")
        if not gid:
            row = conn.execute(
                "SELECT gramps_id FROM minted_media WHERE source_system='immich' AND source_id=?",
                (asset_id,),
            ).fetchone()
            gid = row[0] if row else None

        if gid:
            try:
                media = await gramps.get_media_by_gramps_id(gid)
            except Exception as exc:
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, gramps_id=gid,
                                title=wanted_title(kv, asset, cfg),
                                detail=f"Gramps lookup failed: {str(exc)[:200]}")
                continue
            if media is None:
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, gramps_id=gid,
                                title=wanted_title(kv, asset, cfg),
                                detail=f"synced KV points at {gid}, which is not in Gramps")
                continue
            try:
                cols = update_plan(kv, asset, media, cfg)
            except SyncError as exc:
                # Self-descriptive (unmapped path, unknown gda.date modifier);
                # must not abort the batch.
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, gramps_id=gid,
                                title=wanted_title(kv, asset, cfg),
                                detail=str(exc)[:200])
                continue
            except ValueError as exc:
                # A corrupt/hand-edited gda.date must not abort the batch.
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, gramps_id=gid,
                                title=wanted_title(kv, asset, cfg),
                                detail=f"gda.date is invalid: {str(exc)[:180]}")
                continue
            # An interrupted earlier sync can leave the asset traceable only
            # via minted_media, with no gramps_id in its KV — heal that here
            # (this is the "re-run the sync to finish" path).
            needs_kv = not gk.get("gramps_id")
            if needs_kv:
                cols["kv link"] = f"write {gid} back to gda.gramps"
            if not cols:
                counts["skipped"] += 1
                continue
            if not apply:
                yield SyncEvent(kind="item", entity="media", action="would_update",
                                source_id=asset_id, gramps_id=gid,
                                title=wanted_title(kv, asset, cfg),
                                data={"cols": cols})
                continue
            if selected is not None and f"media:{asset_id}" not in selected:
                continue
            if "title" in cols:
                media["desc"] = wanted_title(kv, asset, cfg)
            if "date" in cols:
                media["date"] = gda_date_to_gramps(kv[cfg.date_key])
            if "file" in cols:
                # The stack's main changed — repoint the media at the new
                # main's file and keep the Immich linkage attributes honest.
                media["path"] = translate_path(asset["originalPath"], cfg.path_mappings)
                media["mime"] = asset.get("originalMimeType") or media.get("mime")
                _set_attr(media, "Immich ID", asset_id)
                if cfg.public_url:
                    _set_attr(media, "Immich URL", f"{cfg.public_url}/photos/{asset_id}")
            try:
                if {"title", "date", "file"} & set(cols):
                    await gramps.update_media(media["handle"], media)
            except Exception as exc:
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="media", action="failed",
                                source_id=asset_id, gramps_id=gid,
                                title=media.get("desc"), detail=str(exc)[:200])
                continue
            if "file" in cols:
                counts["versions_updated"] += 1
                with conn:
                    conn.execute(
                        "UPDATE minted_media SET source_id=? "
                        "WHERE gramps_id=? AND source_system='immich'",
                        (asset_id, gid),
                    )
            if needs_kv:
                healed = {**gk, "schema": 1, "gramps_id": gid}
                healed.setdefault("synced_at", _now())
                try:
                    await immich.put_metadata(asset_id, cfg.gramps_key, healed)
                    counts["kv_healed"] += 1
                except ImmichError as exc:
                    counts["errors"] += 1
                    yield SyncEvent(kind="item", entity="media", action="failed",
                                    source_id=asset_id, gramps_id=gid,
                                    title=media.get("desc"),
                                    detail=f"KV write-back failed: {exc.message[:180]} — re-run the scan")
                    continue
            if "title" in cols:
                counts["titles_updated"] += 1
            if "date" in cols:
                counts["dates_updated"] += 1
            yield SyncEvent(kind="item", entity="media", action="updated",
                            source_id=asset_id, gramps_id=gid,
                            title=media["desc"], data={"cols": cols})
            continue

        # --- unsynced: a set title is the "put this in Gramps" signal -------
        title = (gk.get("title") or "").strip()
        if not title:
            continue
        gd = kv.get(cfg.date_key)
        cols = {"title": title, **({"date": gd.get("display") or "?"} if gd else {})}
        if not apply:
            yield SyncEvent(kind="item", entity="media", action="would_create",
                            source_id=asset_id, title=title, data={"cols": cols})
            continue
        if selected is not None and f"media:{asset_id}" not in selected:
            continue
        try:
            async for ev in sync_one_asset(gramps, immich, conn, cfg, asset_id):
                if ev.kind == "item":
                    if ev.action == "failed":  # e.g. person-link failures
                        counts["errors"] += 1
                    yield ev
                elif ev.kind == "summary":
                    data = ev.data or {}
                    if data.get("created"):
                        counts["created"] += 1
                    if data.get("warning"):
                        # KV write-back failed — the media exists but the
                        # asset can't show its sync state; surface it.
                        counts["errors"] += 1
                        yield SyncEvent(kind="item", entity="media", action="failed",
                                        source_id=asset_id, gramps_id=data.get("gramps_id"),
                                        title=title, detail=str(data["warning"])[:200])
        except SyncError as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, title=title, detail=exc.detail[:200])
        except Exception as exc:  # Gramps/transport/YAML errors — keep the batch going
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="media", action="failed",
                            source_id=asset_id, title=title, detail=str(exc)[:200])

    yield SyncEvent(kind="summary", data=counts)
