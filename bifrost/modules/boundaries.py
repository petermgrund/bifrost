"""Places / boundaries"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
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

# A place's boundary is a GeoJSON map file in its gallery whose OSM URL attribute
# names the OSM object it came from. Gramps Web draws it on the Map.
MAP_FILE_MIME = "application/geo+json"
OSM_URL_ATTR = "OSM URL"
MAP_FILE_STYLE = {"stroke": "#cc2a36", "stroke-width": 2, "fill": "#cc2a36", "fill-opacity": 0.22}


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


def place_name(place: dict) -> str:
    return (place.get("name") or {}).get("value") or place.get("gramps_id") or "?"


def osm_url(osm_type: str, osm_id: int) -> str:
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def map_file(place: dict, geom: dict, osm_type: str, osm_id: int) -> bytes:
    """The boundary as a compact GeoJSON Feature, outlined and filled in red"""
    props = {
        "gramps_id": place.get("gramps_id"),
        "osm_type": osm_type,
        "osm_id": osm_id,
        "name": place_name(place),
    }
    if osm_type == "relation":
        props["relation_id"] = osm_id  # just a legacy key
    feature = {"type": "Feature", "properties": {**props, **MAP_FILE_STYLE}, "geometry": geom}
    return json.dumps(feature, separators=(",", ":")).encode()


def osm_ref(place: dict) -> tuple[str, int] | None:
    for url in place.get("urls", []):
        m = OSM_REF_RE.search(url.get("path") or "")
        if m:
            return m.group(1), int(m.group(2))
    return None


def is_boundary(media: dict) -> bool:
    return media.get("mime") == MAP_FILE_MIME and any(
        a.get("type") == OSM_URL_ATTR for a in media.get("attribute_list") or [])


def boundary_of(place: dict, media_by_handle: dict) -> dict | None:
    """The place's boundary map file, if it has one"""
    for ref in place.get("media_list") or []:
        m = media_by_handle.get(ref.get("ref"))
        if m and is_boundary(m):
            return m
    return None


def boundary_osm(media: dict) -> tuple[str, int] | None:
    """OSM object a map file came from"""
    for a in media.get("attribute_list") or []:
        if a.get("type") == OSM_URL_ATTR:
            m = OSM_REF_RE.search(a.get("value") or "")
            return (m.group(1), int(m.group(2))) if m else None
    return None


def outdated(row: dict) -> bool:
    """Map file built from a different OSM object"""
    return bool(row["has_boundary"] and row["boundary_osm"]
                and row["osm_id"] and row["boundary_osm"] != (row["osm_type"], row["osm_id"]))


async def listing(gramps: GrampsClient, with_boundaries: bool = True) -> list[dict]:
    places = await gramps.list_places_full()
    by_handle = {p["handle"]: p for p in places}
    media = await gramps.list_media(keys="handle,mime,attribute_list") if with_boundaries else []
    media_by_handle = {m["handle"]: m for m in media}

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
        boundary = boundary_of(p, media_by_handle)
        rows.append({
            "handle": p["handle"],
            "gramps_id": gid,
            "name": (p.get("name") or {}).get("value") or gid,
            "hierarchy": hierarchy(p),
            "osm_type": ref[0] if ref else None,
            "osm_id": ref[1] if ref else None,
            "has_coords": bool((p.get("lat") or "").strip() and (p.get("long") or "").strip()),
            "has_boundary": boundary is not None,
            "boundary_osm": boundary_osm(boundary) if boundary else None,
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
        path = osm_url(*osm)
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


async def _unattached(gramps: GrampsClient, content: bytes) -> str | None:
    """A map file with this content that an interrupted run uploaded but never attached"""
    checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
    for m in await gramps.find_media_by_checksum(checksum):
        if m.get("mime") == MAP_FILE_MIME and not any((m.get("backlinks") or {}).values()):
            return m["handle"]
    return None


async def _describe(gramps: GrampsClient, handle: str, place: dict, osm: tuple[str, int]) -> bool:
    """Label a map file and name its OSM object; False when it already was"""
    media = await gramps.get_object("media", handle)
    desc = f"OSM boundary: {place_name(place)}"
    attrs = media.get("attribute_list") or []
    if media.get("desc") == desc and [
            a.get("value") for a in attrs if a.get("type") == OSM_URL_ATTR] == [osm_url(*osm)]:
        return False
    media["desc"] = desc
    media["attribute_list"] = [a for a in attrs if a.get("type") != OSM_URL_ATTR] + [
        {"_class": "Attribute", "type": OSM_URL_ATTR, "value": osm_url(*osm),
         "private": False, "citation_list": [], "note_list": []}]
    await gramps.update_media(handle, media)
    return True


async def _attach(gramps: GrampsClient, place_handle: str, media_handle: str) -> None:
    """Add a map file to the end of the place's gallery"""
    place = await gramps.get_place(place_handle)
    refs = place.get("media_list") or []
    if any(r.get("ref") == media_handle for r in refs):
        return
    place["media_list"] = refs + [{"_class": "MediaRef", "ref": media_handle, "rect": [], "private": False,
                                   "attribute_list": [], "citation_list": [], "note_list": []}]
    await gramps.update_place(place_handle, place)


async def generate_one(gramps: GrampsClient, place_handle: str, force: bool) -> dict:
    """Fetch the place's OSM boundary and keep it as a map file in the place's gallery"""
    place = await gramps.get_place(place_handle, extend="media_list")
    ref = osm_ref(place)
    if ref is None:
        raise BoundaryFetchError(
            f"no OSM URL on place '{place_name(place)}'")
    osm_type, osm_id = ref
    existing = next((m for m in (place.get("extended") or {}).get("media") or []
                     if is_boundary(m)), None)
    result = {"place_handle": place_handle, "osm_type": osm_type,
              "osm_id": osm_id, "gramps_id": place.get("gramps_id")}
    if existing and not force and boundary_osm(existing) in (None, ref):
        return {**result, "media_handle": existing["handle"], "written": False}
    content = map_file(place, await fetch_geojson(osm_type, osm_id), osm_type, osm_id)
    if existing:
        handle = existing["handle"]
        written = await gramps.replace_media_file(handle, content, MAP_FILE_MIME)
    else:
        handle = await _unattached(gramps, content) or await gramps.upload_media(content, MAP_FILE_MIME)
        written = True
    written = await _describe(gramps, handle, place, ref) or written
    if not existing:
        await _attach(gramps, place_handle, handle)
    return {**result, "media_handle": handle, "written": written}


def _progress(label: str, done: int, total: int) -> SyncEvent:
    return SyncEvent(kind="progress", detail=label,
                     data={"done": done, "total": total,
                           "percent": round(100 * done / total) if total else 100})


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


def _boundary_source(row: dict, plan: dict, match: dict) -> tuple[str, int] | None:
    """The OSM area whose boundary the apply should fetch, if any"""
    if "osm" in plan:
        return match["osm_type"], match["osm_id"]
    if row["osm_type"] in ("relation", "way") and (not row["has_boundary"] or outdated(row)):
        return row["osm_type"], row["osm_id"]
    return None


async def _find(row: dict) -> dict | None:
    if row["osm_id"]:
        return await lookup_osm(row["osm_type"], row["osm_id"])
    return await search_osm(", ".join(row["hierarchy"]))


async def scan_links(gramps: GrampsClient, suggestions: dict) -> AsyncIterator[SyncEvent]:
    """Suggest OSM links and coordinates for places missing them"""
    rows = [r for r in await listing(gramps)
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
                if _boundary_source(row, plan, match):
                    plan["boundary"] = "fetch"
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
    gramps: GrampsClient, selected: set[str], suggestions: dict,
) -> AsyncIterator[SyncEvent]:
    """Write accepted OSM links and coordinates to Gramps"""
    by_handle = {r["handle"]: r for r in await listing(gramps)}
    handles = [k.partition(":")[2] for k in selected if k.startswith("place:")]
    todo = [by_handle[h] for h in handles if h in by_handle]
    yield SyncEvent(kind="started", detail=f"{len(todo)} place(s) to update")
    counts = {"linked": 0, "located": 0, "generated": 0, "errors": 0}
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
        if _boundary_source(row, plan, match):
            try:
                result = await generate_one(gramps, row["handle"], force=True)
                counts["generated"] += result["written"]
                plan["boundary"] = "written" if result["written"] else "unchanged"
            except Exception as exc:  # noqa: BLE001
                counts["errors"] += 1
                plan["boundary"] = f"failed: {str(exc)[:160]}"
            if i < len(todo) - 1:
                await asyncio.sleep(1)
        yield SyncEvent(**_row(row), action="created" if "osm" in plan else "updated",
                        data={"cols": {**plan, "match": match["display_name"]}})
    if todo:
        yield _progress("Updating places", len(todo), len(todo))
    yield SyncEvent(kind="summary", data=counts)


async def scan(gramps: GrampsClient) -> AsyncIterator[SyncEvent]:
    """List linked places with missing or outdated boundaries"""
    places = [r for r in await listing(gramps) if r["osm_id"]]
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
                            data={"cols": {"osm": osm, "boundary": f"map file of {old_type} {old_id}"}})
    yield SyncEvent(kind="summary", data={"generated": len(todo), "errors": 0})


async def generate_missing(
    gramps: GrampsClient,
    force: bool = False,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """Add or refresh boundary map files"""
    places = [r for r in await listing(gramps) if r["osm_id"]]
    todo = places if force else [r for r in places if not r["has_boundary"] or outdated(r)]
    if selected is not None:
        todo = [r for r in todo if f"place:{r['handle']}" in selected]
    yield SyncEvent(kind="started",
                    detail=f"{len(todo)} of {len(places)} OSM-linked place(s) to generate")
    counts = {"generated": 0, "errors": 0}
    for i, row in enumerate(todo):
        yield _progress("Fetching boundaries from OpenStreetMap", i, len(todo))
        try:
            result = await generate_one(gramps, row["handle"], force)
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield SyncEvent(**_row(row), action="failed", detail=str(exc))
            continue
        cols = {"osm": f'{row["osm_type"]} {row["osm_id"]}'}
        if result["written"]:
            counts["generated"] += 1
            yield SyncEvent(**_row(row), action="updated" if row["has_boundary"] else "created",
                            data={"cols": cols})
        else:
            yield SyncEvent(**_row(row), action="skipped", detail="boundary unchanged",
                            data={"cols": cols})
        await asyncio.sleep(1)
    if todo:
        yield _progress("Fetching boundaries from OpenStreetMap", len(todo), len(todo))
    yield SyncEvent(kind="summary", data=counts)
