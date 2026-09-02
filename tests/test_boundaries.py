import asyncio
import json

import pytest

from bifrost.modules import boundaries

PLACE = {
    "handle": "ph1", "gramps_id": "P0001",
    "name": {"value": "Norra Ny"},
    "urls": [{"path": "https://www.openstreetmap.org/relation/62411"}],
}
GEOM = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}


class FakeGramps:
    def __init__(self, place=PLACE):
        self.place = place

    async def get_place(self, handle):
        return self.place


def test_write_sidecar_feature_shape(tmp_path):
    sidecar = boundaries.write_sidecar(tmp_path, PLACE, GEOM, "relation", 62411)
    data = json.loads(sidecar.read_text())
    assert sidecar.name == "P0001.geojson"
    assert data["type"] == "Feature" and data["geometry"] == GEOM
    assert data["properties"]["name"] == "Norra Ny"
    assert data["properties"]["relation_id"] == 62411  # legacy key
    way = boundaries.write_sidecar(tmp_path, PLACE, GEOM, "way", 99)
    assert "relation_id" not in json.loads(way.read_text())["properties"]


def test_generate_one_idempotent(tmp_path, monkeypatch):
    calls = []

    async def fake_fetch(osm_type, osm_id, **kw):
        calls.append((osm_type, osm_id))
        return GEOM

    monkeypatch.setattr(boundaries, "fetch_geojson", fake_fetch)
    gr = FakeGramps()

    r1 = asyncio.run(boundaries.generate_one(gr, tmp_path, "ph1", force=False))
    assert r1["written"] is True and calls == [("relation", 62411)]
    assert (tmp_path / "P0001.geojson").is_file()

    r2 = asyncio.run(boundaries.generate_one(gr, tmp_path, "ph1", force=False))
    assert r2["written"] is False and len(calls) == 1

    r3 = asyncio.run(boundaries.generate_one(gr, tmp_path, "ph1", force=True))
    assert r3["written"] is True and len(calls) == 2


def test_generate_one_requires_osm_url(tmp_path):
    gr = FakeGramps({"handle": "ph2", "gramps_id": "P0002",
                     "name": {"value": "Nowhere"}, "urls": []})
    with pytest.raises(boundaries.BoundaryFetchError):
        asyncio.run(boundaries.generate_one(gr, tmp_path, "ph2", force=False))


PLACE_UNLINKED = {"handle": "ph2", "gramps_id": "P0002", "name": {"value": "Nowhere"}, "urls": []}
PLACE_WAY = {"handle": "ph3", "gramps_id": "P0003", "name": {"value": "Kyrkan"},
             "urls": [{"path": "https://www.openstreetmap.org/way/77"}]}


class ListingGramps(FakeGramps):
    def __init__(self, places):
        self.places = {p["handle"]: p for p in places}

    async def list_places_full(self):
        return list(self.places.values())

    async def get_place(self, handle):
        return self.places[handle]


def _events(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


def test_boundary_scan_lists_linked_places(tmp_path):
    gr = ListingGramps([PLACE, PLACE_UNLINKED, PLACE_WAY])
    boundaries.write_sidecar(tmp_path, PLACE_WAY, GEOM, "way", 77)
    events = _events(boundaries.scan(gr, tmp_path))
    rows = [e for e in events if e.kind == "item"]
    assert [(e.entity, e.source_id, e.gramps_id, e.action) for e in rows] == [
        ("place", "ph1", "P0001", "would_create")]
    assert rows[0].title == "Norra Ny" and rows[0].data["cols"] == {"osm": "relation 62411"}
    assert events[-1].data == {"generated": 1, "errors": 0}


def test_generate_missing_honours_selection_and_reports_progress(tmp_path, monkeypatch):
    calls = []

    async def fake_fetch(osm_type, osm_id, **kw):
        calls.append((osm_type, osm_id))
        return GEOM

    monkeypatch.setattr(boundaries, "fetch_geojson", fake_fetch)
    monkeypatch.setattr(boundaries.asyncio, "sleep", _no_sleep)
    gr = ListingGramps([PLACE, PLACE_UNLINKED, PLACE_WAY])
    events = _events(boundaries.generate_missing(gr, tmp_path, selected={"place:ph3"}))
    assert calls == [("way", 77)]
    rows = [e for e in events if e.kind == "item"]
    assert [(e.source_id, e.action) for e in rows] == [("ph3", "created")]
    progress = [e.data for e in events if e.kind == "progress"]
    assert [d["done"] for d in progress] == [0, 1] and {d["total"] for d in progress} == {1}
    assert (tmp_path / "P0003.geojson").is_file() and not (tmp_path / "P0001.geojson").exists()


async def _no_sleep(_seconds):
    return None


PLACE_PARENT = {"handle": "ph-mn", "gramps_id": "P0100", "name": {"value": "Minnesota"}, "urls": []}
PLACE_CHILD = {"handle": "ph-hc", "gramps_id": "P0101", "name": {"value": "Hennepin County"},
               "urls": [], "placeref_list": [{"ref": "ph-mn"}]}


class LinkingGramps(ListingGramps):
    def __init__(self, places):
        super().__init__(places)
        self.updated = []

    async def update_place(self, handle, place):
        self.places[handle] = place
        self.updated.append(handle)


def test_listing_builds_the_name_hierarchy_and_reads_sidecar_origin(tmp_path):
    boundaries.write_sidecar(tmp_path, PLACE, GEOM, "relation", 99)
    rows = {r["gramps_id"]: r for r in asyncio.run(
        boundaries.listing(LinkingGramps([PLACE, PLACE_PARENT, PLACE_CHILD]), tmp_path))}
    assert rows["P0101"]["hierarchy"] == ["Hennepin County", "Minnesota"]
    assert rows["P0001"]["boundary_osm"] == ("relation", 99)
    assert boundaries.outdated(rows["P0001"]) and not boundaries.outdated(rows["P0101"])


PLACE_LOCATED = {"handle": "ph-cc", "gramps_id": "P0102", "name": {"value": "Center City"},
                 "lat": "45.393900", "long": "-92.816600", "urls": [], "placeref_list": [{"ref": "ph-mn"}]}
PLACE_FARM = {"handle": "ph-farm", "gramps_id": "P0103", "name": {"value": "Lindqvist farm"},
              "urls": [], "placeref_list": [{"ref": "ph-mn"}]}


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
                "display_name": "Norra Ny, Värmland, Sverige"}

    monkeypatch.setattr(boundaries, "search_osm", fake_search)
    monkeypatch.setattr(boundaries, "lookup_osm", fake_lookup)
    monkeypatch.setattr(boundaries.asyncio, "sleep", _no_sleep)
    return searches, lookups


def test_link_scan_suggests_links_and_coordinates(tmp_path, monkeypatch):
    searches, lookups = _fake_osm(monkeypatch)
    gr = LinkingGramps([PLACE, PLACE_PARENT, PLACE_CHILD, PLACE_LOCATED, PLACE_FARM])
    suggestions = {}
    events = _events(boundaries.scan_links(gr, tmp_path, suggestions))
    rows = {e.gramps_id: e for e in events if e.kind == "item"}
    assert lookups == [("relation", 62411)]
    assert sorted(searches) == ["Center City, Minnesota", "Hennepin County, Minnesota",
                                "Lindqvist farm, Minnesota", "Minnesota"]
    assert rows["P0101"].action == "would_create"
    assert rows["P0101"].data["cols"] == {"osm": "relation 1795848", "coordinates": "45.0000, -93.4000",
                                          "match": "Hennepin County, Minnesota, United States"}
    assert rows["P0102"].action == "would_create"
    assert set(rows["P0102"].data["cols"]) == {"osm", "match"}
    assert rows["P0103"].action == "would_update"
    assert set(rows["P0103"].data["cols"]) == {"coordinates", "match"}
    assert rows["P0001"].action == "would_update"
    assert rows["P0001"].data["cols"]["coordinates"] == "60.5000, 13.2000"
    assert "P0100" not in rows
    assert events[-1].data == {"linked": 2, "located": 3, "unmatched": 1, "errors": 0}
    assert set(suggestions) == {"ph-hc", "ph-cc", "ph-farm", "ph1"}

    events = _events(boundaries.apply_links(
        gr, tmp_path, {"place:ph-hc", "place:ph-cc", "place:ph-farm", "place:ph1"}, suggestions))
    done = {e.gramps_id: e.action for e in events if e.kind == "item"}
    assert done == {"P0101": "created", "P0102": "created", "P0103": "updated", "P0001": "updated"}
    assert boundaries.osm_ref(gr.places["ph-hc"]) == ("relation", 1795848)
    assert (gr.places["ph-hc"]["lat"], gr.places["ph-hc"]["long"]) == ("45.000000", "-93.400000")
    assert (gr.places["ph-cc"]["lat"], gr.places["ph-cc"]["long"]) == ("45.393900", "-92.816600")
    assert boundaries.osm_ref(gr.places["ph-farm"]) is None
    assert gr.places["ph-farm"]["lat"] == "45.360000"
    assert boundaries.osm_ref(gr.places["ph1"]) == ("relation", 62411)
    assert gr.places["ph1"]["long"] == "13.200000"
    assert suggestions == {}


def test_boundary_scan_flags_an_outdated_sidecar_and_regenerates_it(tmp_path, monkeypatch):
    calls = []

    async def fake_fetch(osm_type, osm_id, **kw):
        calls.append((osm_type, osm_id))
        return GEOM

    monkeypatch.setattr(boundaries, "fetch_geojson", fake_fetch)
    monkeypatch.setattr(boundaries.asyncio, "sleep", _no_sleep)
    boundaries.write_sidecar(tmp_path, PLACE, GEOM, "relation", 99)
    gr = ListingGramps([PLACE])
    rows = [e for e in _events(boundaries.scan(gr, tmp_path)) if e.kind == "item"]
    assert [(e.gramps_id, e.action) for e in rows] == [("P0001", "would_update")]
    assert rows[0].data["cols"] == {"osm": "relation 62411", "boundary": "relation 99 on disk"}
    events = _events(boundaries.generate_missing(gr, tmp_path, selected={"place:ph1"}))
    assert calls == [("relation", 62411)]
    assert [e.action for e in events if e.kind == "item"] == ["updated"]
    assert boundaries.sidecar_osm(tmp_path, "P0001") == ("relation", 62411)
