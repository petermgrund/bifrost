"""Gramps places and their OpenStreetMap links"""

from __future__ import annotations

import asyncio
import re
from typing import AsyncIterator

import httpx

from ..core.clients import GrampsClient
from ..core.events import SyncEvent

OSM_REF_RE = re.compile(r"openstreetmap\.org/(relation|way)/(\d+)")

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
NOMINATIM_PAUSE_S = 1.1
LINK_SCAN_CAP = 50
USER_AGENT = "bifrost/1.0 (self-hosted genealogy tool)"


def place_name(place: dict) -> str:
    return (place.get("name") or {}).get("value") or place.get("gramps_id") or "?"


def osm_url(osm_type: str, osm_id: int) -> str:
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def osm_ref(place: dict) -> tuple[str, int] | None:
    for url in place.get("urls", []):
        m = OSM_REF_RE.search(url.get("path") or "")
        if m:
            return m.group(1), int(m.group(2))
    return None


async def listing(gramps: GrampsClient) -> list[dict]:
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
        rows.append({
            "handle": p["handle"],
            "gramps_id": gid,
            "name": (p.get("name") or {}).get("value") or gid,
            "hierarchy": hierarchy(p),
            "osm_type": ref[0] if ref else None,
            "osm_id": ref[1] if ref else None,
            "has_coords": bool((p.get("lat") or "").strip() and (p.get("long") or "").strip()),
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
        if i < len(todo) - 1:
            await asyncio.sleep(1)
    if todo:
        yield _progress("Updating places", len(todo), len(todo))
    yield SyncEvent(kind="summary", data=counts)
