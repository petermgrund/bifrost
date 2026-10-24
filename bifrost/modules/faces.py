"""Faces: Immich people linked to Gramps persons through the Immich Person ID attribute"""

from __future__ import annotations

import logging
import sqlite3
from typing import AsyncIterator

from ..core.clients import GrampsClient, ImmichClient
from ..core.clients.gramps import person_display_name
from ..core.clients.immich import ImmichError
from ..core.events import SyncEvent, progress
from .sync_immich import (
    PERSON_ATTR,
    _attr,
    _merged_details,
    _user_id,
    link_asset_faces,
    load_person_map,
    new_face_results,
    owner_client,
)

log = logging.getLogger("bifrost.faces")


def _person_name(person: dict) -> str:
    return (person.get("name") or "").strip()


def person_ids(person: dict) -> list[str]:
    """The Immich person ids a Gramps person carries"""
    return [a["value"].strip() for a in person.get("attribute_list") or []
            if a.get("type") == PERSON_ATTR and (a.get("value") or "").strip()]


def people_index(people: list[dict]) -> list[dict]:
    """The Faces page's Gramps people with their media counts and Immich person ids, by name"""
    return sorted(
        ({"handle": p["handle"], "name": person_display_name(p), "gramps_id": p.get("gramps_id", ""),
          "media_count": len(p.get("media_list") or []),
          "rect_count": sum(1 for mr in p.get("media_list") or [] if mr.get("rect")),
          "immich_ids": person_ids(p)} for p in people),
        key=lambda r: r["name"].lower())


async def _unlink(gramps: GrampsClient, handle: str, ids: set[str] | None) -> bool:
    """Take the given Immich people (all of them for None) off a Gramps person"""
    person = await gramps.get_person(handle, ok_404=True)
    if person is None:
        return False
    attrs = person.get("attribute_list") or []
    kept = [a for a in attrs if not (a.get("type") == PERSON_ATTR
                                    and (ids is None or (a.get("value") or "").strip() in ids))]
    if len(kept) == len(attrs):
        return False
    person["attribute_list"] = kept
    await gramps.update_person(handle, person)
    return True


async def set_link(gramps: GrampsClient, linked: dict[str, str], handle: str,
                   immich_person_id: str) -> None:
    """Put an Immich person on one Gramps person: added there, taken off any other"""
    other = linked.get(immich_person_id)
    if other and other != handle:
        await _unlink(gramps, other, {immich_person_id})
    person = await gramps.get_person(handle)
    if immich_person_id in person_ids(person):
        return
    person.setdefault("attribute_list", []).append(_attr(PERSON_ATTR, immich_person_id))
    await gramps.update_person(handle, person)


async def delete_link(gramps: GrampsClient, handle: str) -> bool:
    return await _unlink(gramps, handle, None)


async def adopt_person_links(conn: sqlite3.Connection, gramps: GrampsClient) -> int:
    """Move the rows of the old person_links table onto the Gramps people, then drop the table"""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='person_links'").fetchone():
        return 0
    moved = 0
    for r in conn.execute("SELECT gramps_handle, immich_person_id FROM person_links").fetchall():
        person = await gramps.get_person(r["gramps_handle"], ok_404=True)
        if person is None:
            log.warning("person link for %s dropped: no such Gramps person", r["gramps_handle"])
            continue
        if r["immich_person_id"] in person_ids(person):
            continue
        person.setdefault("attribute_list", []).append(_attr(PERSON_ATTR, r["immich_person_id"]))
        await gramps.update_person(r["gramps_handle"], person)
        moved += 1
    with conn:
        conn.execute("DROP TABLE person_links")
    if moved:
        log.info("moved %d person link(s) onto the Gramps people", moved)
    return moved


async def resolve_person(accounts, person_id: str) -> dict | None:
    """Which account knows this person"""
    for client in accounts:
        try:
            p = await client.get_person(person_id)
        except ImmichError:
            continue
        try:
            uid = await _user_id(client)
        except ImmichError:
            uid = ""
        return {"name": _person_name(p),
                "owner_user_id": uid,
                "account_label": getattr(client, "label", "")}
    return None


async def _people_by_account(accounts):
    """(client, uid, label, people) per REACHABLE account"""
    out = []
    for client in accounts:
        try:
            uid = await _user_id(client)
            people = await client.list_people()
        except ImmichError:
            continue
        out.append((client, uid, getattr(client, "label", ""), people))
    return out


async def merged_people(accounts) -> list[dict]:
    """Reachable accounts' people listings, labeled, named people first"""
    out = []
    for _client, uid, label, people in await _people_by_account(accounts):
        for p in people:
            out.append({"id": p["id"], "name": _person_name(p),
                        "is_hidden": p.get("isHidden", False),
                        "owner_user_id": uid, "account_label": label})
    out.sort(key=lambda r: (r["name"] == "", r["name"].lower()))
    return out


async def grouped_links(accounts, people: list[dict]) -> list[dict]:
    """One entry per linked Gramps person, its Immich people named and placed in their accounts"""
    by_id: dict[str, dict] = {}
    for _client, uid, label, listed in await _people_by_account(accounts):
        for p in listed:
            by_id.setdefault(p["id"], {"name": _person_name(p),
                                       "owner_user_id": uid, "account_label": label})
    out = []
    for row in people:
        if not row["immich_ids"]:
            continue
        links = []
        for pid in row["immich_ids"]:
            info = by_id.get(pid)
            if info is None:
                info = await resolve_person(accounts, pid)
            links.append({"gramps_handle": row["handle"], "immich_person_id": pid,
                          "person_name": (info or {}).get("name", ""),
                          "account_label": (info or {}).get("account_label", ""),
                          "resolved": info is not None})
        out.append({"gramps_handle": row["handle"], "links": links})
    return out


async def person_thumbnail_bytes(accounts, person_id: str) -> tuple[bytes, str]:
    """The first account that serves the thumbnail wins; a hard error beats a 404"""
    errors: list[ImmichError] = []
    for client in accounts:
        try:
            return await client.person_thumbnail(person_id)
        except ImmichError as exc:
            errors.append(exc)
    hard = next((e for e in errors if e.status not in (400, 404)), None)
    raise hard or (errors[0] if errors
                   else ImmichError(404, "no Immich account configured"))


async def apply_links(
    gramps: GrampsClient,
    accounts: list[ImmichClient],
    conn: sqlite3.Connection,
    apply: bool,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    person_map = await load_person_map(gramps)
    counts = {"faces_linked": 0, "boxes_added": 0, "unreadable": 0, "errors": 0}
    if not person_map:
        yield SyncEvent(kind="error", detail="no person links yet")
        yield SyncEvent(kind="summary", data=counts)
        return

    rows = conn.execute(
        "SELECT gramps_id, source_id FROM minted_media WHERE source_system='immich' AND withdrawn_at IS NULL"
    ).fetchall()
    if selected is not None:
        rows = [r for r in rows if f"face:{r['source_id']}" in selected]
    yield SyncEvent(
        kind="started",
        detail=f"{len(rows)} synced media to scan against {len(person_map)} link(s)")
    if not rows:
        yield SyncEvent(kind="summary", data=counts)
        return

    yield progress("Checking faces", 0, len(rows))
    media_by_gid = {
        m["gramps_id"]: m for m in await gramps.list_media() if m.get("gramps_id")}
    details = await _merged_details(accounts, [r["source_id"] for r in rows])

    for i, r in enumerate(rows):
        yield progress("Checking faces", i, len(rows))
        asset = details.get(r["source_id"])
        media = media_by_gid.get(r["gramps_id"])
        title = ((media or {}).get("desc") or (asset or {}).get("originalFileName")
                 or r["source_id"])
        if asset is None or media is None:
            counts["unreadable"] += 1
            yield SyncEvent(
                kind="item", entity="face", action="failed",
                source_id=r["source_id"], gramps_id=r["gramps_id"], title=title,
                detail="asset detail unreadable" if asset is None
                       else "no Gramps media with this id")
            continue
        faces_client, account_err = await owner_client(accounts, asset)
        if account_err:
            yield SyncEvent(
                kind="item", entity="face", action="failed",
                source_id=r["source_id"], gramps_id=r["gramps_id"], title=title,
                detail=account_err)
        results = new_face_results()
        async for ev in link_asset_faces(
                gramps, faces_client, asset, r["source_id"], media["handle"],
                r["gramps_id"], person_map, results, apply=apply):
            if ev.kind != "item":
                yield ev
                continue
            person = ev.title or "?"
            row = dict(kind="item", entity="face", source_id=r["source_id"],
                       gramps_id=r["gramps_id"], title=title)
            if ev.action == "created":
                counts["faces_linked"] += 1
                yield SyncEvent(**row, action="created" if apply else "would_create",
                                data={"cols": {person: "link"}})
            elif ev.action == "updated":
                counts["boxes_added"] += 1
                yield SyncEvent(**row, action="updated" if apply else "would_update",
                                data={"cols": {person: "face box"}})
            elif ev.action == "failed":
                counts["errors"] += 1
                yield SyncEvent(**row, action="failed",
                                detail=f"{person}: {ev.detail}" if ev.title else ev.detail)
            else:
                yield ev
    yield progress("Checking faces", len(rows), len(rows))
    yield SyncEvent(kind="summary", data=counts)
