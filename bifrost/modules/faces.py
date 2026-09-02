"""Faces"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import yaml

from ..core.clients import GrampsClient, ImmichClient
from ..core.events import SyncEvent
from ..core.clients.immich import ImmichError
from .sync_immich import (
    _merged_details,
    _user_id,
    link_asset_faces,
    new_face_results,
    person_links_map,
    owner_client,
)

log = logging.getLogger("bifrost.faces")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _person_name(person: dict) -> str:
    """padded name sorts"""
    return (person.get("name") or "").strip()


def list_links(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT gramps_handle, immich_person_id, label, owner_user_id, created_at "
        "FROM person_links ORDER BY label, gramps_handle"
    ).fetchall()
    return [dict(r) for r in rows]


def set_link(
    conn: sqlite3.Connection, gramps_handle: str, immich_person_id: str,
    label: str = "", owner_user_id: str | None = None,
) -> None:
    """One link per Immich person"""
    with conn:
        conn.execute(
            "DELETE FROM person_links WHERE immich_person_id=?",
            (immich_person_id,))
        if owner_user_id is None:
            conn.execute(
                "DELETE FROM person_links WHERE gramps_handle=?",
                (gramps_handle,))
        else:
            # NULL-owner rows are of unknown account a definite relink
            # replaces them too, or the one-per-account rule could break
            conn.execute(
                "DELETE FROM person_links WHERE gramps_handle=? "
                "AND (owner_user_id=? OR owner_user_id IS NULL)",
                (gramps_handle, owner_user_id))
        conn.execute(
            "INSERT INTO person_links "
            "(gramps_handle, immich_person_id, label, owner_user_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (gramps_handle, immich_person_id, label.strip(), owner_user_id, _now()),
        )


def delete_link(conn: sqlite3.Connection, gramps_handle: str) -> bool:
    with conn:
        cur = conn.execute(
            "DELETE FROM person_links WHERE gramps_handle=?", (gramps_handle,))
    return cur.rowcount > 0


def import_person_map_yaml(conn: sqlite3.Connection, path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    if conn.execute("SELECT 1 FROM person_links LIMIT 1").fetchone():
        return 0
    raw = yaml.safe_load(path.read_text()) or {}
    entries = [
        e for e in (raw.get("people") or [])
        if e.get("gramps_handle") and e.get("immich_person_id")
    ]
    with conn:
        for e in entries:
            conn.execute(
                "INSERT OR REPLACE INTO person_links "
                "(gramps_handle, immich_person_id, label, created_at) "
                "VALUES (?, ?, ?, ?)",
                (e["gramps_handle"], e["immich_person_id"],
                 (e.get("label") or "").strip(), _now()),
            )
    if entries:
        log.info("imported %d person link(s) from %s", len(entries), path)
    return len(entries)


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


async def enrich_links(accounts, conn: sqlite3.Connection) -> list[dict]:
    """Links joined with person names and accounts; lazily backfills
    owner_user_id on legacy rows"""
    by_id: dict[str, dict] = {}
    for _client, uid, label, people in await _people_by_account(accounts):
        for p in people:
            by_id.setdefault(p["id"], {
                "name": _person_name(p),
                "owner_user_id": uid, "account_label": label})
    out = []
    for row in list_links(conn):
        info = by_id.get(row["immich_person_id"])
        if info is None:
            info = await resolve_person(accounts, row["immich_person_id"])
        if info and info["owner_user_id"] and not row["owner_user_id"]:
            with conn:
                conn.execute(
                    "UPDATE person_links SET owner_user_id=? "
                    "WHERE gramps_handle=? AND immich_person_id=?",
                    (info["owner_user_id"], row["gramps_handle"],
                     row["immich_person_id"]))
            row["owner_user_id"] = info["owner_user_id"]
        out.append({**row,
                    "person_name": (info or {}).get("name", ""),
                    "account_label": (info or {}).get("account_label", ""),
                    "resolved": info is not None})
    return out


async def person_thumbnail_bytes(
    accounts, conn: sqlite3.Connection, person_id: str,
) -> tuple[bytes, str]:
    """Thumbnail via the owning account first"""
    ordered = list(accounts)
    row = conn.execute(
        "SELECT owner_user_id FROM person_links WHERE immich_person_id=?",
        (person_id,)).fetchone()
    owner = row["owner_user_id"] if row and row["owner_user_id"] else None
    if owner and len(ordered) > 1:
        first, rest = [], []
        for client in ordered:
            try:
                uid = await _user_id(client)
            except ImmichError:
                uid = ""
            (first if uid == owner else rest).append(client)
        ordered = first + rest
    errors: list[ImmichError] = []
    for client in ordered:
        try:
            return await client.person_thumbnail(person_id)
        except ImmichError as exc:
            errors.append(exc)
    hard = next((e for e in errors if e.status not in (400, 404)), None)
    raise hard or (errors[0] if errors
                   else ImmichError(404, "no Immich account configured"))


async def grouped_links(accounts, conn: sqlite3.Connection) -> list[dict]:
    """One entry per Gramps person"""
    groups: dict[str, dict] = {}
    for row in await enrich_links(accounts, conn):
        g = groups.setdefault(row["gramps_handle"], {
            "gramps_handle": row["gramps_handle"], "label": "", "links": []})
        g["links"].append(row)
        if not g["label"]:
            g["label"] = row["label"] or row["person_name"]
    return list(groups.values())


async def apply_links(
    gramps: GrampsClient,
    accounts: list[ImmichClient],
    conn: sqlite3.Connection,
    apply: bool,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    person_map = person_links_map(conn)
    counts = {"faces_linked": 0, "boxes_added": 0, "unreadable": 0, "errors": 0}
    if not person_map:
        yield SyncEvent(kind="error", detail="no person links yet")
        yield SyncEvent(kind="summary", data=counts)
        return

    rows = conn.execute(
        "SELECT gramps_id, source_id FROM minted_media WHERE source_system='immich'"
    ).fetchall()
    if selected is not None:
        rows = [r for r in rows if f"face:{r['source_id']}" in selected]
    yield SyncEvent(
        kind="started",
        detail=f"{len(rows)} synced media to scan against {len(person_map)} link(s)")
    if not rows:
        yield SyncEvent(kind="summary", data=counts)
        return

    def progress(done: int) -> SyncEvent:
        return SyncEvent(kind="progress", detail="Checking faces",
                         data={"done": done, "total": len(rows),
                               "percent": round(100 * done / len(rows))})

    yield progress(0)
    media_by_gid = {
        m["gramps_id"]: m for m in await gramps.list_media() if m.get("gramps_id")}
    details = await _merged_details(accounts, [r["source_id"] for r in rows])

    for i, r in enumerate(rows):
        yield progress(i)
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
    yield progress(len(rows))
    yield SyncEvent(kind="summary", data=counts)
