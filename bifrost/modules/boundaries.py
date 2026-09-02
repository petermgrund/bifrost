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
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
NOMINATIM_PAUSE_S = 1.1
LINK_SCAN_CAP = 50
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


def sidecar_osm(boundaries_dir: Path | None, gramps_id: str) -> tuple[str, int] | None:
    """OSM object a sidecar came from"""
    if not boundaries_dir or not gramps_id:
        return None
    try:
        props = json.loads((boundaries_dir / f"{gramps_id}.geojson").read_text()).get("properties") or {}
        return (props.get("osm_type") or "relation", int(props["osm_id"]))
    except (OSError, ValueError, TypeError, KeyError):
        return None


def outdated(row: dict) -> bool:
    """Sidecar built from a different OSM object"""
    return bool(row["has_boundary"] and row["boundary_osm"]
                and row["osm_id"] and row["boundary_osm"] != (row["osm_type"], row["osm_id"]))


async def listing(gramps: GrampsClient, boundaries_dir: Path | None) -> list[dict]:
    places = await gramps.list_places_full()
    by_handle = {p["handle"]: p for p in places}

    def hierarchy(place: dict) -> list[str]:
        """Place names, innermost first"""
        names, seen, cur = [], set(), place
        while cur and cur["handle"] not in seen:
            seen.add(cur["handle"])
            names.append((cur.get("name") or {}).get("value") or cur.get("gramps_id") or "")
            refs = cur.get("placeref_list") or []
            cur = by_handle.get(refs[0].get("ref")) if refs else None
        return [n for n in names if n]

    rows = []
    for p in places:
        gid = p.get("gramps_id", "")
        ref = osm_ref(p)
        has_geojson = bool(
            boundaries_dir and gid and (boundaries_dir / f"{gid}.geojson").is_file())
        rows.append({
            "handle": p["handle"],
            "gramps_id": gid,
            "name": (p.get("name") or {}).get("value") or gid,
            "hierarchy": hierarchy(p),
            "osm_type": ref[0] if ref else None,
            "osm_id": ref[1] if ref else None,
            "has_coords": bool((p.get("lat") or "").strip() and (p.get("long") or "").strip()),
            "has_boundary": has_geojson,
            "boundary_osm": sidecar_osm(boundaries_dir, gid) if has_geojson else None,
        })
    rows.sort(key=lambda r: r["name"].lower())
    return rows


def _match(r: dict) -> dict:
    out = {"osm_type": r["osm_type"], "osm_id": int(r["osm_id"]),
           "display_name": r.get("display_name") or ""}
    try:
        out["lat"], out["lon"] = float(r["lat"]), float(r["lon"])
    except (KeyError, TypeError, ValueError):
        pass
    return out


async def _nominatim(path: str, params: dict, timeout: float) -> list[dict]:
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(f"{NOMINATIM_BASE}/{path}", params={**params, "format": "jsonv2"})
        resp.raise_for_status()
        data = resp.json()
    return [r for r in data if r.get("osm_type") and r.get("osm_id")] if isinstance(data, list) else []


async def search_osm(query: str, *, timeout: float = 20.0) -> dict | None:
    """Nominatim's best area, else its best point"""
    results = await _nominatim("search", {"q": query, "limit": 5}, timeout)
    best = next((r for r in results if r["osm_type"] in ("relation", "way")), None) \
        or (results[0] if results else None)
    return _match(best) if best else None


async def lookup_osm(osm_type: str, osm_id: int, *, timeout: float = 20.0) -> dict | None:
    """Nominatim's record for one OSM object"""
    results = await _nominatim("lookup", {"osm_ids": f"{osm_type[0].upper()}{osm_id}"}, timeout)
    return _match(results[0]) if results else None


async def write_place(
    gramps: GrampsClient, handle: str, osm: tuple[str, int] | None = None,
    coords: tuple[float, float] | None = None, replace: bool = False,
) -> dict:
    """Write an OSM link and/or coordinates to a place"""
    place = await gramps.get_place(handle)
    if osm:
        existing = osm_ref(place)
        if existing and not replace:
            raise ValueError("place already has OSM URL")
        path = f"https://www.openstreetmap.org/{osm[0]}/{osm[1]}"
        if existing:
            for url in place.get("urls", []):
                if OSM_REF_RE.search(url.get("path") or ""):
                    url["path"] = path
                    break
        else:
            place.setdefault("urls", []).append({
                "_class": "Url", "path": path, "desc": "", "type": "OSM URL", "private": False,
            })
    if coords:
        place["lat"], place["long"] = f"{coords[0]:.6f}", f"{coords[1]:.6f}"
    await gramps.update_place(handle, place)
    return place


async def set_relation(
    gramps: GrampsClient, handle: str, osm_type: str, osm_id: int, replace: bool = False,
) -> dict:
    """Write an OSM link to a place"""
    await write_place(gramps, handle, osm=(osm_type, osm_id), replace=replace)
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


def _progress(label: str, done: int, total: int) -> SyncEvent:
    return SyncEvent(kind="progress", detail=label,
                     data={"done": done, "total": total,
                           "percent": round(100 * done / total) if total else 100,
                           "band_index": 0, "band_count": 1})


def _row(row: dict) -> dict:
    """Row fields, keyed place:<handle>"""
    return dict(kind="item", entity="place", source_id=row["handle"],
                gramps_id=row["gramps_id"], title=row["name"])


def _osm(match: dict) -> str:
    return f'{match["osm_type"]} {match["osm_id"]}'


def _plan(row: dict, match: dict) -> dict:
    """What a match adds to a place"""
    plan = {}
    if not row["osm_id"] and match["osm_type"] in ("relation", "way"):
        plan["osm"] = _osm(match)
    if not row["has_coords"] and "lat" in match:
        plan["coordinates"] = f'{match["lat"]:.4f}, {match["lon"]:.4f}'
    return plan


async def _find(row: dict) -> dict | None:
    if row["osm_id"]:
        return await lookup_osm(row["osm_type"], row["osm_id"])
    return await search_osm(", ".join(row["hierarchy"]))


async def scan_links(
    gramps: GrampsClient, boundaries_dir: Path | None, suggestions: dict,
) -> AsyncIterator[SyncEvent]:
    """Suggest OSM links and coordinates for places missing them"""
    rows = [r for r in await listing(gramps, boundaries_dir)
            if not r["osm_id"] or not r["has_coords"]]
    todo = rows[:LINK_SCAN_CAP]
    scope = f"{len(rows)} place(s) without an OpenStreetMap link or coordinates"
    if len(rows) > len(todo):
        scope += f"; searching the first {len(todo)}"
    yield SyncEvent(kind="started", detail=scope)
    counts = {"linked": 0, "located": 0, "unmatched": 0, "errors": 0}
    for i, row in enumerate(todo):
        yield _progress("Searching OpenStreetMap", i, len(todo))
        try:
            match = await _find(row)
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield SyncEvent(**_row(row), action="failed",
                            detail=f"OpenStreetMap search failed: {str(exc)[:160]}")
        else:
            plan = _plan(row, match) if match else {}
            if not plan:
                counts["unmatched"] += 1
            else:
                suggestions[row["handle"]] = match
                counts["linked"] += "osm" in plan
                counts["located"] += "coordinates" in plan
                yield SyncEvent(**_row(row),
                                action="would_create" if "osm" in plan else "would_update",
                                data={"cols": {**plan, "match": match["display_name"]},
                                      "suggestion": match})
        if i < len(todo) - 1:
            await asyncio.sleep(NOMINATIM_PAUSE_S)
    if todo:
        yield _progress("Searching OpenStreetMap", len(todo), len(todo))
    yield SyncEvent(kind="summary", data=counts)


async def apply_links(
    gramps: GrampsClient, boundaries_dir: Path | None, selected: set[str], suggestions: dict,
) -> AsyncIterator[SyncEvent]:
    """Write accepted OSM links and coordinates to Gramps"""
    by_handle = {r["handle"]: r for r in await listing(gramps, boundaries_dir)}
    handles = [k.partition(":")[2] for k in selected if k.startswith("place:")]
    todo = [by_handle[h] for h in handles if h in by_handle]
    yield SyncEvent(kind="started", detail=f"{len(todo)} place(s) to update")
    counts = {"linked": 0, "located": 0, "errors": 0}
    for i, row in enumerate(todo):
        yield _progress("Updating places", i, len(todo))
        match = suggestions.get(row["handle"])
        if match is None:
            try:
                match = await _find(row)
            except Exception as exc:  # noqa: BLE001
                counts["errors"] += 1
                yield SyncEvent(**_row(row), action="failed",
                                detail=f"OpenStreetMap search failed: {str(exc)[:160]}")
                continue
        plan = _plan(row, match) if match else {}
        if not plan:
            counts["errors"] += 1
            yield SyncEvent(**_row(row), action="failed", detail="no OpenStreetMap match")
            continue
        try:
            await write_place(
                gramps, row["handle"],
                osm=(match["osm_type"], match["osm_id"]) if "osm" in plan else None,
                coords=(match["lat"], match["lon"]) if "coordinates" in plan else None)
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield SyncEvent(**_row(row), action="failed", detail=str(exc)[:200])
            continue
        suggestions.pop(row["handle"], None)
        counts["linked"] += "osm" in plan
        counts["located"] += "coordinates" in plan
        yield SyncEvent(**_row(row), action="created" if "osm" in plan else "updated",
                        data={"cols": {**plan, "match": match["display_name"]}})
    if todo:
        yield _progress("Updating places", len(todo), len(todo))
    yield SyncEvent(kind="summary", data=counts)


async def scan(gramps: GrampsClient, boundaries_dir: Path) -> AsyncIterator[SyncEvent]:
    """List linked places with missing or outdated boundaries"""
    places = [r for r in await listing(gramps, boundaries_dir) if r["osm_id"]]
    todo = [r for r in places if not r["has_boundary"] or outdated(r)]
    yield SyncEvent(kind="started",
                    detail=f"{len(todo)} of {len(places)} OSM-linked place(s) without a current boundary")
    for row in todo:
        osm = f'{row["osm_type"]} {row["osm_id"]}'
        if not row["has_boundary"]:
            yield SyncEvent(**_row(row), action="would_create", data={"cols": {"osm": osm}})
        else:
            old_type, old_id = row["boundary_osm"]
            yield SyncEvent(**_row(row), action="would_update",
                            data={"cols": {"osm": osm, "boundary": f"{old_type} {old_id} on disk"}})
    yield SyncEvent(kind="summary", data={"generated": len(todo), "errors": 0})


async def generate_missing(
    gramps: GrampsClient,
    boundaries_dir: Path,
    force: bool = False,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """Write boundary sidecars"""
    places = [r for r in await listing(gramps, boundaries_dir) if r["osm_id"]]
    todo = places if force else [r for r in places if not r["has_boundary"] or outdated(r)]
    if selected is not None:
        todo = [r for r in todo if f"place:{r['handle']}" in selected]
    yield SyncEvent(kind="started",
                    detail=f"{len(todo)} of {len(places)} OSM-linked place(s) to generate")
    counts = {"generated": 0, "errors": 0}
    for i, row in enumerate(todo):
        yield _progress("Fetching boundaries from OpenStreetMap", i, len(todo))
        try:
            await generate_one(gramps, boundaries_dir, row["handle"], force or outdated(row))
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield SyncEvent(**_row(row), action="failed", detail=str(exc))
            continue
        counts["generated"] += 1
        yield SyncEvent(**_row(row), action="updated" if row["has_boundary"] else "created",
                        data={"cols": {"osm": f'{row["osm_type"]} {row["osm_id"]}'}})
        await asyncio.sleep(1)
    if todo:
        yield _progress("Fetching boundaries from OpenStreetMap", len(todo), len(todo))
    yield SyncEvent(kind="summary", data=counts)
