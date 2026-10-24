import asyncio
import copy
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from bifrost.modules import places
from bifrost.web.routes import places as places_routes

PLACE = {"handle": "ph1", "gramps_id": "P0001", "name": {"value": "Norra Ny"},
         "urls": [{"path": "https://www.openstreetmap.org/relation/62411"}]}
PLACE_PARENT = {"handle": "ph-mn", "gramps_id": "P0100", "name": {"value": "Minnesota"}, "urls": []}
PLACE_CHILD = {"handle": "ph-hc", "gramps_id": "P0101", "name": {"value": "Hennepin County"},
               "urls": [], "placeref_list": [{"ref": "ph-mn"}]}
PLACE_LOCATED = {"handle": "ph-cc", "gramps_id": "P0102", "name": {"value": "Center City"},
                 "lat": "45.393900", "long": "-92.816600", "urls": [], "placeref_list": [{"ref": "ph-mn"}]}
PLACE_FARM = {"handle": "ph-farm", "gramps_id": "P0103", "name": {"value": "Lindqvist farm"},
              "urls": [], "placeref_list": [{"ref": "ph-mn"}]}


def _events(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


async def _no_sleep(_seconds):
    return None


class FakeGramps:
    def __init__(self, places=()):
        self.places = {p["handle"]: copy.deepcopy(p) for p in places}
        self.updated = []

    async def list_places_full(self):
        return copy.deepcopy(list(self.places.values()))

    async def get_place(self, handle, **params):
        return copy.deepcopy(self.places[handle])

    async def get_place_by_gramps_id(self, gramps_id):
        return next((copy.deepcopy(p) for p in self.places.values() if p["gramps_id"] == gramps_id), None)

    async def update_place(self, handle, place):
        self.places[handle] = copy.deepcopy(place)
        self.updated.append(handle)


def _fake_osm(monkeypatch):
    searches, lookups = [], []

    async def fake_search(query, **kw):
        searches.append(query)
        if query.startswith("Hennepin County"):
            return {"osm_type": "relation", "osm_id": 1795848, "lat": 45.0, "lon": -93.4,
                    "display_name": "Hennepin County, Minnesota, United States"}
        if query.startswith("Center City"):
            return {"osm_type": "relation", "osm_id": 137256, "lat": 45.39, "lon": -92.82,
                    "display_name": "Center City, Chisago County, Minnesota, United States"}
        if query.startswith("Lindqvist farm"):
            return {"osm_type": "node", "osm_id": 555, "lat": 45.36, "lon": -92.85,
                    "display_name": "Lindqvist, Chisago County, Minnesota, United States"}
        return None

    async def fake_lookup(osm_type, osm_id, **kw):
        lookups.append((osm_type, osm_id))
        return {"osm_type": osm_type, "osm_id": osm_id, "lat": 60.5, "lon": 13.2,
                "display_name": f"{osm_type} {osm_id}, Värmland, Sverige"}

    monkeypatch.setattr(places, "search_osm", fake_search)
    monkeypatch.setattr(places, "lookup_osm", fake_lookup)
    monkeypatch.setattr(places.asyncio, "sleep", _no_sleep)
    return searches, lookups


def test_listing_reads_links_coordinates_and_hierarchy():
    rows = {r["gramps_id"]: r for r in asyncio.run(places.listing(
        FakeGramps([PLACE, PLACE_PARENT, PLACE_CHILD, PLACE_LOCATED])))}
    assert rows["P0101"]["hierarchy"] == ["Hennepin County", "Minnesota"]
    assert (rows["P0001"]["osm_type"], rows["P0001"]["osm_id"], rows["P0001"]["has_coords"]) == ("relation", 62411, False)
    assert rows["P0102"]["osm_id"] is None and rows["P0102"]["has_coords"]
    assert [r["name"] for r in asyncio.run(places.listing(FakeGramps([PLACE, PLACE_PARENT])))] == ["Minnesota", "Norra Ny"]


def test_link_scan_suggests_links_and_coordinates(monkeypatch):
    searches, lookups = _fake_osm(monkeypatch)
    gr = FakeGramps([PLACE, PLACE_PARENT, PLACE_CHILD, PLACE_LOCATED, PLACE_FARM])
    suggestions = {}
    events = _events(places.scan_links(gr, suggestions))
    rows = {e.gramps_id: e for e in events if e.kind == "item"}
    assert lookups == [("relation", 62411)]
    assert sorted(searches) == ["Center City, Minnesota", "Hennepin County, Minnesota",
                                "Lindqvist farm, Minnesota", "Minnesota"]
    assert rows["P0101"].action == "would_create"
    assert rows["P0101"].data["cols"] == {"osm": "relation 1795848", "coordinates": "45.0000, -93.4000",
                                          "match": "Hennepin County, Minnesota, United States"}
    assert rows["P0102"].action == "would_create" and set(rows["P0102"].data["cols"]) == {"osm", "match"}
    assert rows["P0103"].action == "would_update" and set(rows["P0103"].data["cols"]) == {"coordinates", "match"}
    assert rows["P0001"].action == "would_update"
    assert rows["P0001"].data["cols"]["coordinates"] == "60.5000, 13.2000"
    assert "P0100" not in rows
    assert events[-1].data == {"linked": 2, "located": 3, "unmatched": 1, "errors": 0}
    assert set(suggestions) == {"ph-hc", "ph-cc", "ph-farm", "ph1"}

    events = _events(places.apply_links(
        gr, {"place:ph-hc", "place:ph-cc", "place:ph-farm", "place:ph1"}, suggestions))
    done = {e.gramps_id: e.action for e in events if e.kind == "item"}
    assert done == {"P0101": "created", "P0102": "created", "P0103": "updated", "P0001": "updated"}
    assert places.osm_ref(gr.places["ph-hc"]) == ("relation", 1795848)
    assert (gr.places["ph-hc"]["lat"], gr.places["ph-hc"]["long"]) == ("45.000000", "-93.400000")
    assert (gr.places["ph-cc"]["lat"], gr.places["ph-cc"]["long"]) == ("45.393900", "-92.816600")
    assert places.osm_ref(gr.places["ph-farm"]) is None
    assert gr.places["ph-farm"]["lat"] == "45.360000"
    assert places.osm_ref(gr.places["ph1"]) == ("relation", 62411)
    assert gr.places["ph1"]["long"] == "13.200000"
    assert suggestions == {}
    assert events[-1].data == {"linked": 2, "located": 3, "errors": 0}


def test_link_apply_reports_a_failed_search(monkeypatch):
    _fake_osm(monkeypatch)

    async def boom(query, **kw):
        raise httpx.ConnectError("nominatim is down")

    monkeypatch.setattr(places, "search_osm", boom)
    gr = FakeGramps([PLACE_PARENT, PLACE_CHILD])
    events = _events(places.apply_links(gr, {"place:ph-hc"}, {}))
    row = [e for e in events if e.kind == "item"][0]
    assert row.action == "failed" and "OpenStreetMap search failed" in row.detail
    assert gr.updated == [] and events[-1].data == {"linked": 0, "located": 0, "errors": 1}


def _app(gramps):
    app = FastAPI()
    app.include_router(places_routes.router)
    app.state.gramps = gramps
    app.state.cfg = SimpleNamespace()
    app.state.caches = {}
    app.state.conn = __import__("bifrost.core.db", fromlist=["connect"]).connect(
        __import__("pathlib").Path(__import__("tempfile").mkdtemp()) / "t.db")
    return app


def _call(app, method, url, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bifrost") as c:
            return await c.request(method, url, **kw)
    return asyncio.run(go())


def test_links_route(monkeypatch):
    _fake_osm(monkeypatch)
    gr = FakeGramps([PLACE_PARENT, PLACE_CHILD])
    app = _app(gr)
    assert _call(app, "GET", "/places/api/links/config").json() == {"enabled": True}
    assert _call(app, "GET", "/places").headers["location"] == "/#other"
    r = _call(app, "POST", "/places/api/links/preview")
    assert r.status_code == 200 and r.json()["apply"] is False
    [row] = [e for e in r.json()["events"] if e["kind"] == "item"]
    assert (row["source_id"], row["action"], row["data"]["cols"]["osm"]) == ("ph-hc", "would_create", "relation 1795848")
    assert _call(app, "POST", "/places/api/links/apply", json={"selected": []}).status_code == 400
    r = _call(app, "POST", "/places/api/links/apply", json={"selected": ["place:ph-hc"]})
    assert r.status_code == 200 and [e["action"] for e in r.json()["events"] if e["kind"] == "item"] == ["created"]
    assert places.osm_ref(gr.places["ph-hc"]) == ("relation", 1795848)
