"""Hand the photo facts in Immich and Bifrost's tables over to the Gramps media objects"""

from __future__ import annotations

import asyncio
import csv
import sqlite3
from pathlib import Path
from typing import AsyncIterator

from ..core.clients import GrampsClient, ImmichClient
from ..core.clients.immich import ImmichError
from ..core.config import SyncImmichConfig
from ..core.events import SyncEvent
from . import photos
from . import sync_immich as si
from .sync_immich import SyncError

CSV_FIELDS = ("gramps_id", "asset_id", "field", "gramps_value", "immich_value", "keep")
KEEP_IMMICH = "immich"
DECIDED_FIELDS = ("title", "date", "place")
UNTAG_PAUSE = 1.0


def _item(entity: str, action: str, gid: str | None, asset_id: str, title: str | None = None,
          detail: str | None = None, data: dict | None = None) -> SyncEvent:
    return SyncEvent(kind="item", entity=entity, action=action, source_id=asset_id, gramps_id=gid,
                     title=title, detail=detail, data=data)


async def registered(conn: sqlite3.Connection, accounts: list[ImmichClient]) -> list[tuple[str, str, list[str]]]:
    """(gramps_id, main asset id, every asset id of its stack) for each registered photo"""
    stacks, members_of = await photos._stack_index(accounts)
    out = []
    for r in conn.execute("SELECT gramps_id, source_id FROM minted_media WHERE source_system='immich' "
                          "ORDER BY gramps_id"):
        st = stacks.get(r["source_id"])
        main = (st[1] or r["source_id"]) if st else r["source_id"]
        members = members_of.get(st[0], []) if st else []
        out.append((r["gramps_id"], main, list(dict.fromkeys([main, r["source_id"], *members]))))
    return out


def note_rows(conn: sqlite3.Connection, gid: str, asset_ids: list[str]) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT asset_id, text FROM photo_notes WHERE gramps_id=? "
        f"OR asset_id IN ({','.join('?' * len(asset_ids))}) ORDER BY updated_at DESC, asset_id",
        (gid, *asset_ids)).fetchall()
    return [r for r in rows if (r["text"] or "").strip()]


def link_rows(conn: sqlite3.Connection, asset_ids: list[str]) -> list[str]:
    rows = conn.execute(
        f"SELECT url FROM photo_links WHERE asset_id IN ({','.join('?' * len(asset_ids))}) ORDER BY id",
        asset_ids).fetchall()
    return list(dict.fromkeys(r["url"] for r in rows))


def waiting_links(conn: sqlite3.Connection, registered_ids: set[str]) -> int:
    """Links kept for photos not in Gramps yet"""
    return sum(1 for r in conn.execute("SELECT asset_id FROM photo_links") if r["asset_id"] not in registered_ids)


def disagreements(asset: dict, media: dict, holders: list[dict], cfg: SyncImmichConfig) -> list[tuple[str, str, str]]:
    """(field, Gramps value, Immich value) where the two sides differ on title, date or place"""
    out = []
    immich_title = si.split_description((asset.get("exifInfo") or {}).get("description") or "")[0]
    if immich_title and immich_title != (media.get("desc") or ""):
        out.append(("title", media.get("desc") or "", immich_title))
    form = photos.date_form(asset)
    if form and not si.dates_equal(media.get("date"), photos.gramps_date(form)):
        out.append(("date", photos.gramps_date_text(media.get("date")), form["display"]))
    tag_gid = si.place_tag_value(asset, cfg)
    gramps_gids = [h.get("gramps_id") or "" for h in holders]
    if tag_gid and tag_gid not in gramps_gids:
        out.append(("place", ", ".join(gramps_gids), tag_gid))
    return out


def read_decisions(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    missing = set(CSV_FIELDS) - set(rows[0] if rows else CSV_FIELDS)
    if missing:
        raise SyncError(400, f"{path} lacks the columns {', '.join(sorted(missing))}")
    return [r for r in rows if (r.get("keep") or "").strip().lower() == KEEP_IMMICH]


async def dry_run(gramps: GrampsClient, accounts: list[ImmichClient], conn: sqlite3.Connection,
                  cfg: SyncImmichConfig, out: Path) -> AsyncIterator[SyncEvent]:
    """Refuse while a sync is pending, else write the decisions CSV and say what --apply would do"""
    yield SyncEvent(kind="started", detail=f"photos handover dry run, decisions to {out}")
    found = await registered(conn, accounts)
    blocked = 0
    for gid, aid, _members in found:
        try:
            pending = await photos.pending_changes(gramps, accounts, conn, cfg, aid)
        except Exception as exc:  # noqa: BLE001
            blocked += 1
            yield _item("media", "failed", gid, aid, detail=f"pending check failed: {str(exc)[:200]}")
            continue
        if pending == ["media"]:
            yield _item("media", "failed", gid, aid, detail=f"the register points at {gid}, which is not in Gramps")
        elif pending:
            blocked += 1
            yield _item("media", "failed", gid, aid, detail="pending sync changes: " + ", ".join(pending))
    if blocked:
        yield SyncEvent(kind="summary", detail="run Sync first", data={"blocked": blocked})
        return

    rows: list[dict] = []
    plan = {"disagreements": 0, "notes": 0, "url_notes": 0, "note_choices": 0, "links": 0}
    for gid, aid, members in found:
        try:
            asset = await si._merged_one(accounts, aid)
        except SyncError as exc:
            yield _item("media", "failed", gid, aid, detail=exc.detail)
            continue
        media, notes, holders, error = await photos._gramps_side(gramps, gid)
        if media is None:
            continue
        for field, gramps_value, immich_value in disagreements(asset, media, holders, cfg):
            plan["disagreements"] += 1
            rows.append({"gramps_id": gid, "asset_id": aid, "field": field, "gramps_value": gramps_value,
                         "immich_value": immich_value, "keep": ""})
            yield _item("media", "would_update", gid, aid, media.get("desc"),
                        data={"cols": {field: f"{gramps_value!r} (Gramps) / {immich_value!r} (Immich)"}})
        kept = note_rows(conn, gid, members)
        if len(kept) > 1:
            current = si.note_text(si.first_media_note(notes)).strip()
            for row in kept:
                plan["note_choices"] += 1
                rows.append({"gramps_id": gid, "asset_id": row["asset_id"], "field": "note",
                             "gramps_value": current, "immich_value": row["text"].strip(), "keep": ""})
            yield _item("note", "would_update", gid, aid, media.get("desc"),
                        detail=f"{len(kept)} note rows, mark one keep={KEEP_IMMICH}")
        elif kept:
            plan["url_notes" if si.is_url_line(kept[0]["text"]) else "notes"] += 1
        plan["links"] += len(link_rows(conn, members))
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    waiting = waiting_links(conn, {m for _gid, _aid, members in found for m in members})
    yield SyncEvent(kind="summary", detail="dry run",
                    data={**plan, "links_waiting": waiting, "rows": len(rows), "csv": str(out)})


async def apply(gramps: GrampsClient, accounts: list[ImmichClient], conn: sqlite3.Connection,
                cfg: SyncImmichConfig, decisions: Path) -> AsyncIterator[SyncEvent]:
    """Write the keep=immich rows, Bifrost's notes and links onto the media objects"""
    yield SyncEvent(kind="started", detail=f"photos handover apply from {decisions}")
    picked = read_decisions(decisions)
    found = await registered(conn, accounts)
    counts = {"titles": 0, "dates": 0, "places": 0, "notes": 0, "links": 0, "errors": 0}
    for gid, aid, members in found:
        wanted = {r["field"] for r in picked if r["gramps_id"] == gid and r["field"] in DECIDED_FIELDS}
        note_picks = {r["asset_id"] for r in picked if r["gramps_id"] == gid and r["field"] == "note"}
        kept = note_rows(conn, gid, members)
        texts = [r["text"].strip() for r in kept
                 if len(kept) == 1 or r["asset_id"] in note_picks]
        links = link_rows(conn, members) + [t for t in texts if si.is_url_line(t)]
        if not wanted and not texts and not links:
            continue
        try:
            asset = await si._merged_one(accounts, aid)
        except SyncError as exc:
            counts["errors"] += 1
            yield _item("media", "failed", gid, aid, detail=exc.detail)
            continue
        media, _notes, holders, error = await photos._gramps_side(gramps, gid)
        if media is None:
            counts["errors"] += 1
            yield _item("media", "failed", gid, aid, detail=error)
            continue
        changed: dict = {}
        if "title" in wanted:
            title = si.split_description((asset.get("exifInfo") or {}).get("description") or "")[0]
            if title and title != (media.get("desc") or ""):
                media["desc"] = title
                changed["title"] = title
                counts["titles"] += 1
        if "date" in wanted:
            form = photos.date_form(asset)
            if form and not si.dates_equal(media.get("date"), photos.gramps_date(form)):
                media["date"] = photos.gramps_date(form)
                changed["date"] = form["display"]
                counts["dates"] += 1
        new_links = [u for u in dict.fromkeys(links) if u not in si.media_links(media)]
        if new_links and si.set_media_links(media, si.media_links(media) + new_links):
            changed["links"] = f"{len(new_links)} added"
            counts["links"] += len(new_links)
        try:
            if changed:
                await gramps.update_media(media["handle"], media)
                yield _item("media", "updated", gid, aid, media.get("desc"), data={"cols": changed})
            for text in texts:
                if si.is_url_line(text):
                    continue
                action = await si.append_media_note(gramps, media, text)
                if action:
                    counts["notes"] += 1
                    yield _item("note", action, gid, aid, media.get("desc"),
                                data={"cols": {"note": f"{len(text)} chars"}})
            if "place" in wanted:
                tag_gid = si.place_tag_value(asset, cfg)
                new_place = await gramps.get_place_by_gramps_id(tag_gid) if tag_gid else None
                if new_place is None:
                    counts["errors"] += 1
                    yield _item("place", "failed", gid, aid, detail=f"{tag_gid} names no Gramps place")
                elif len(holders) > 1:
                    counts["errors"] += 1
                    yield _item("place", "failed", gid, aid, detail="in more than one gallery, left alone")
                elif await photos.move_place(gramps, media["handle"], holders[0] if holders else None, new_place):
                    counts["places"] += 1
                    yield _item("place", "updated", gid, aid, si.place_label(new_place),
                                data={"cols": {"place": si.place_label(new_place)}})
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield _item("media", "failed", gid, aid, media.get("desc"), detail=str(exc)[:200])
    waiting = waiting_links(conn, {m for _gid, _aid, members in found for m in members})
    yield SyncEvent(kind="summary", detail="applied", data={**counts, "links_waiting": waiting})


def stripped_tags(own: set[str], cfg: SyncImmichConfig) -> set[str]:
    """The owner's tags the handover removes: Bifrost's date, place and field-sync tags"""
    exact = {si.TAG_SYNC_DESCRIPTION, si.TAG_SYNC_DATE, si.TAG_SYNC_LOCATION, cfg.note_sync_tag.lower()}
    prefix = cfg.place_tag_prefix.lower() + "/" if cfg.place_tag_prefix else None
    return {t for t in own if t in exact or t in photos.DATE_TAGS or si.is_span_tag(t)
            or (prefix and t.startswith(prefix))}


async def strip_tags(client: ImmichClient, asset_id: str, remove: set[str], keep: set[str]) -> list[str]:
    """Take tags off one call at a time, paused so Immich's sidecar writes do not collide, then put back
    any kept tag the re-read shows gone; returns the tags put back"""
    index = {(t.get("value") or "").lower(): t for t in await client.list_tags()}
    for low in sorted(remove):
        tag = index.get(low)
        if tag:
            await client.untag_asset(tag["id"], asset_id)
            await asyncio.sleep(UNTAG_PAUSE)
    await asyncio.sleep(UNTAG_PAUSE)
    lost = sorted(keep - si.tag_values(await client.get_asset(asset_id)))
    ids = [index[t]["id"] for t in lost if t in index]
    if ids:
        await client.tag_assets(ids, [asset_id])
    return lost


async def cleanup_tags(accounts: list[ImmichClient], conn: sqlite3.Connection,
                       cfg: SyncImmichConfig) -> AsyncIterator[SyncEvent]:
    """Take the Date, Place and field-sync tags off every registered photo and its versions"""
    yield SyncEvent(kind="started", detail="photos handover tag cleanup")
    counts = {"cleaned": 0, "skipped": 0, "put_back": 0, "errors": 0}
    for gid, _aid, members in await registered(conn, accounts):
        for member in members:
            try:
                asset = await si._merged_one(accounts, member)
            except SyncError as exc:
                counts["errors"] += 1
                yield _item("tag", "failed", gid, member, detail=exc.detail)
                continue
            own = si.owner_tag_values(asset)
            if own is None:
                counts["errors"] += 1
                yield _item("tag", "failed", gid, member, detail="cannot tell which account owns this asset")
                continue
            remove = stripped_tags(own, cfg)
            if not remove:
                counts["skipped"] += 1
                continue
            client, _probe = await si.owner_client(accounts, asset)
            try:
                lost = await strip_tags(client, member, remove, own - remove)
            except ImmichError as exc:
                counts["errors"] += 1
                yield _item("tag", "failed", gid, member, detail=exc.message)
                continue
            counts["cleaned"] += 1
            yield _item("tag", "updated", gid, member, detail="removed " + ", ".join(sorted(remove)))
            if lost:
                counts["put_back"] += len(lost)
                yield _item("tag", "updated", gid, member,
                            detail="put back " + ", ".join(lost) + ", which Immich had dropped")
    yield SyncEvent(kind="summary", detail="tags cleaned", data=counts)
