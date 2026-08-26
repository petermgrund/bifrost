"""Places / boundaries"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import AsyncIterator

import httpx

from ..core.clients import GrampsClient
from ..core.events import SyncEvent

log = logging.getLogger("bifrost.boundaries")
OSM_REF_RE = re.compile(r"openstreetmap\.org/(relation|way)/(\d+)")

POLYGONS_BASE = "https://polygons.openstreetmap.fr"
OSM_API_BASE = "https://api.openstreetmap.org/api/0.6"
USER_AGENT = "bifrost/1.0 (self-hosted genealogy tool)"


class BoundaryFetchError(Exception):
    pass


async def fetch_geojson(osm_type: str, osm_id: int, *, timeout: float = 30.0) -> dict:
    if osm_type == "way":
        return await fetch_way_geojson(osm_id, timeout=timeout)
    return await fetch_relation_geojson(osm_id, timeout=timeout)


async def fetch_way_geojson(way_id: int, *, timeout: float = 30.0) -> dict:
    """A way is an ordered node. must be closed (first node == last) to be an area."""
    async with httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = await client.get(f"{OSM_API_BASE}/way/{way_id}/full.json")
        if resp.status_code in (404, 410):
            raise BoundaryFetchError(
                f"way {way_id} does not exist on OSM")
        resp.raise_for_status()
        elements = resp.json().get("elements") or []

    nodes = {e["id"]: (e["lon"], e["lat"]) for e in elements if e.get("type") == "node"}
    way = next((e for e in elements
                if e.get("type") == "way" and e.get("id") == way_id), None)
    if way is None:
        raise BoundaryFetchError(f"OSM API response for way {way_id} held no way element")
    nds = way.get("nodes") or []
    if len(nds) < 4 or nds[0] != nds[-1]:
        raise BoundaryFetchError(
            f"way {way_id} is not a closed ring")
    try:
        ring = [[*nodes[n]] for n in nds]
    except KeyError as e:
        raise BoundaryFetchError(f"way {way_id} references missing node {e}")
    return {"type": "Polygon", "coordinates": [ring]}


async def fetch_relation_geojson(relation_id: int, *, timeout: float = 30.0) -> dict:
    """polygons.openstreetmap.fr stitches a relation's ways"""
    async with httpx.AsyncClient(timeout=timeout) as client:
        geo = await _try_get_geojson(client, relation_id)
        if geo is not None:
            return geo
        await client.get(f"{POLYGONS_BASE}/", params={"id": relation_id})
        for _ in range(6):
            await asyncio.sleep(5)
            geo = await _try_get_geojson(client, relation_id)
            if geo is not None:
                return geo
    raise BoundaryFetchError(
        f"polygons.openstreetmap.fr did not return a boundary for relation "
        f"{relation_id} within the polling window. Try again in a bit")


async def _try_get_geojson(client: httpx.AsyncClient, relation_id: int) -> dict | None:
    resp = await client.get(
        f"{POLYGONS_BASE}/get_geojson.py", params={"id": relation_id, "params": "0"})
    resp.raise_for_status()
    if not resp.text.strip():
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    if not isinstance(data, dict) or "type" not in data:
        return None
    return data


def write_sidecar(
    boundaries_dir: Path, place: dict, geom: dict, osm_type: str, osm_id: int,
) -> Path:
    """Write the boundary as a GeoJSON Feature keyed by the place's gramps_id"""
    gramps_id = place.get("gramps_id")
    if not gramps_id:
        raise BoundaryFetchError("place has no gramps_id")
    name = (place.get("name") or {}).get("value") or gramps_id
    feature = {
        "type": "Feature",
        "properties": {
            "gramps_id": gramps_id,
            "osm_type": osm_type,
            "osm_id": osm_id,
            "name": name,
        },
        "geometry": geom,
    }
    if osm_type == "relation":
        feature["properties"]["relation_id"] = osm_id  # just a legacy key
    boundaries_dir.mkdir(parents=True, exist_ok=True)
    sidecar = boundaries_dir / f"{gramps_id}.geojson"
    sidecar.write_text(json.dumps(feature))
    return sidecar


def osm_ref(place: dict) -> tuple[str, int] | None:
    for url in place.get("urls", []):
        m = OSM_REF_RE.search(url.get("path") or "")
        if m:
            return m.group(1), int(m.group(2))
    return None


async def listing(gramps: GrampsClient, boundaries_dir: Path | None) -> list[dict]:
    rows = []
    for p in await gramps.list_places_full():
        gid = p.get("gramps_id", "")
        ref = osm_ref(p)
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
    existing = osm_ref(place)
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


async def generate_one(
    gramps: GrampsClient, boundaries_dir: Path, place_handle: str, force: bool,
) -> dict:
    """Fetch the place's OSM boundary and write its GeoJSON sidecar"""
    place = await gramps.get_place(place_handle)
    name = (place.get("name") or {}).get("value") or place.get("gramps_id") or "?"
    ref = osm_ref(place)
    if ref is None:
        raise BoundaryFetchError(
            f"no OSM URL on place '{name}'")
    osm_type, osm_id = ref
    gramps_id = place.get("gramps_id")
    sidecar = boundaries_dir / f"{gramps_id}.geojson" if gramps_id else None
    if sidecar is not None and sidecar.exists() and not force:
        return {"place_handle": place_handle, "osm_type": osm_type,
                "osm_id": osm_id, "gramps_id": gramps_id, "written": False}
    geom = await fetch_geojson(osm_type, osm_id)
    write_sidecar(boundaries_dir, place, geom, osm_type, osm_id)
    return {"place_handle": place_handle, "osm_type": osm_type,
            "osm_id": osm_id, "gramps_id": gramps_id, "written": True}


async def generate_missing(
    gramps: GrampsClient,
    boundaries_dir: Path,
    force: bool = False,
) -> AsyncIterator[SyncEvent]:
    places = [r for r in await listing(gramps, boundaries_dir) if r["osm_id"]]
    todo = places if force else [r for r in places if not r["has_boundary"]]
    yield SyncEvent(kind="started",
                    detail=f"{len(todo)} of {len(places)} OSM-tagged place(s) to generate")
    counts = {"generated": 0, "errors": 0}
    for row in todo:
        try:
            await generate_one(gramps, boundaries_dir, row["handle"], force)
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
