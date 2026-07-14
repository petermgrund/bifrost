"""Single-asset Immich → Gramps media sync.

Reduced re-add (2026-07-14) of the integration removed in 77cf402. The old
tag-driven bulk sync is gone: urd (:8768) triggers the initial sync of one
asset at a time via POST /sync/immich/asset. Differences from the old design:

- Faces become plain person↔media associations (MediaRef with rect: []) —
  no bounding boxes, no face_pads.
- The Gramps date comes ONLY from the asset's gda.date KV entry (a
  Gramps-model date maintained by urd). No gda.date → no date on the media
  object. Never Immich's timestamp.
- The media title comes from the gda.gramps KV entry's "title", falling back
  to the original filename.
- After a successful sync, gda.gramps gets gramps_id/synced_at written back
  so urd can show sync state. A re-run for an already-synced asset finishes
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

    try:
        kv = await immich.get_metadata(asset_id)
    except ImmichError as exc:
        raise SyncError(502, f"could not read asset metadata: {exc.message}")
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
