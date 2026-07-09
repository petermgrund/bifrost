"""Places / boundaries """

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import AsyncIterator

import httpx

from ..core.clients import GrampsClient
from ..core.events import SyncEvent

log = logging.getLogger("bifrost.boundaries")
OSM_REF_RE = re.compile(r"openstreetmap\.org/(relation|way)/(\d+)")


def osm_ref_from_place(place: dict) -> tuple[str, int] | None:
    for url in place.get("urls", []):
        m = OSM_REF_RE.search(url.get("path") or "")
        if m:
            return m.group(1), int(m.group(2))
    return None


async def listing(gramps: GrampsClient, boundaries_dir: Path | None) -> list[dict]:
    rows = []
    for p in await gramps.list_places_full():
        gid = p.get("gramps_id", "")
        ref = osm_ref_from_place(p)
        has_geojson = bool(
            boundaries_dir and gid and (boundaries_dir / f"{gid}.geojson").is_file())
        rows.append({
            "handle": p["handle"],
            "gramps_id": gid,
            "name": (p.get("name") or {}).get("value") or gid,
            "osm_type": ref[0] if ref else None,
            "osm_id": ref[1] if ref else None,
            "has_boundary": has_geojson,
        })
    rows.sort(key=lambda r: r["name"].lower())
    return rows


async def set_relation(
    gramps: GrampsClient, handle: str, osm_type: str, osm_id: int, replace: bool = False,
) -> dict:
    place = await gramps.get_place(handle)
    existing = osm_ref_from_place(place)
    if existing and not replace:
        raise ValueError("place already has OSM URL")
    path = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    if existing:
        for url in place.get("urls", []):
            if OSM_REF_RE.search(url.get("path") or ""):
                url["path"] = path
                break
    else:
        place.setdefault("urls", []).append({
            "_class": "Url",
            "path": path,
            "desc": "",
            "type": "OSM URL",
            "private": False,
        })
    await gramps.update_place(handle, place)
    return {"handle": handle, "osm_type": osm_type, "osm_id": osm_id}


async def generate_one(service_url: str, place_handle: str, force: bool) -> dict:
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(f"{service_url}/generate",
                                 json={"place_handle": place_handle, "force": force})
        if resp.status_code >= 400:
            raise RuntimeError(f"{resp.status_code}: {resp.text[:300]}")
        return resp.json()


async def generate_missing(
    gramps: GrampsClient,
    service_url: str,
    boundaries_dir: Path | None,
    force: bool = False,
) -> AsyncIterator[SyncEvent]:
    places = [r for r in await listing(gramps, boundaries_dir) if r["osm_id"]]
    todo = places if force else [r for r in places if not r["has_boundary"]]
    yield SyncEvent(kind="started",
                    detail=f"{len(todo)} of {len(places)} OSM-tagged place(s) to generate")
    counts = {"generated": 0, "errors": 0}
    for row in todo:
        try:
            await generate_one(service_url, row["handle"], force)
        except Exception as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="place", action="failed",
                            gramps_id=row["gramps_id"], title=row["name"],
                            detail=str(exc))
            continue
        counts["generated"] += 1
        yield SyncEvent(kind="item", entity="place",
                        action="updated" if row["has_boundary"] else "created",
                        gramps_id=row["gramps_id"], title=row["name"],
                        data={"cols": {"osm": f'{row["osm_type"]} {row["osm_id"]}'}})
        await asyncio.sleep(1)
    yield SyncEvent(kind="summary", data=counts)
