import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.modules import boundaries
from bifrost.web.routes import places as places_routes

PLACE = {
    "handle": "ph1", "gramps_id": "P0001",
    "name": {"value": "Norra Ny"},
    "urls": [{"path": "https://www.openstreetmap.org/relation/62411"}],
}
GEOM = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
NEW_GEOM = {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 0]]]}
PHOTO = {"handle": "photo", "gramps_id": "O0001", "mime": "image/jpeg", "desc": "Church",
         "checksum": "", "attribute_list": []}


def osm_attr(osm_type, osm_id):
    return {"_class": "Attribute", "type": "OSM URL",
            "value": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
            "private": False, "citation_list": [], "note_list": []}


def map_file_media(handle, osm_type, osm_id, **extra):
    """A boundary map file as migrate_boundaries_to_map_files.py leaves it"""
    return {"handle": handle, "gramps_id": f"O{handle}", "mime": "application/geo+json",
            "desc": "OSM boundary: Norra Ny", "checksum": "",
            "attribute_list": [osm_attr(osm_type, osm_id)], **extra}


def run(coro):
    return asyncio.run(coro)


def _events(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


async def _no_sleep(_seconds):
    return None


class FakeGramps:
    """Places, media and media files in memory, behind the client calls the boundaries module makes"""

    def __init__(self, places=(), media=()):
        self.places = {p["handle"]: copy.deepcopy(p) for p in places}
        self.media = {m["handle"]: copy.deepcopy(m) for m in media}
        self.files = {}
        self.media_listings = []
        self.uploads = []
        self.updated = []

    async def list_places_full(self):
        return copy.deepcopy(list(self.places.values()))

    async def list_media(self, keys=None):
        self.media_listings.append(keys)
        wanted = keys.split(",") if keys else None
        return [{k: copy.deepcopy(v) for k, v in m.items() if wanted is None or k in wanted}
                for m in self.media.values()]

    async def get_place(self, handle, extend=None):
        place = copy.deepcopy(self.places[handle])
        if extend == "media_list":
            place["extended"] = {"media": [copy.deepcopy(self.media[r["ref"]])
                                           for r in place.get("media_list") or []]}
        return place

    async def get_place_by_gramps_id(self, gramps_id):
        return next((copy.deepcopy(p) for p in self.places.values() if p["gramps_id"] == gramps_id), None)

    async def update_place(self, handle, place):
        self.places[handle] = copy.deepcopy(place)
        self.updated.append(handle)

    async def get_object(self, api_path, handle):
        assert api_path == "media"
        return copy.deepcopy(self.media[handle])

    async def update_media(self, handle, media):
        self.media[handle] = copy.deepcopy(media)

    async def upload_media(self, content, mime):
        handle = f"m{len(self.media) + 1}"
        self.media[handle] = {"handle": handle, "gramps_id": f"O{handle}", "mime": mime, "desc": "",
                              "checksum": hashlib.md5(content).hexdigest(), "attribute_list": []}
        self.files[handle] = content
        self.uploads.append(handle)
        return handle

    async def replace_media_file(self, handle, content, mime):
        if self.files.get(handle) == content:
            return False  # Gramps answers 409
        self.files[handle] = content
        self.media[handle].update(mime=mime, checksum=hashlib.md5(content).hexdigest())
        return True

    async def find_media_by_checksum(self, checksum):
        def backlinks(handle):
            refs = [p["handle"] for p in self.places.values()
                    if any(r["ref"] == handle for r in p.get("media_list") or [])]
            return {"place": refs} if refs else {}
        return [{**copy.deepcopy(m), "backlinks": backlinks(m["handle"])}
                for m in self.media.values() if m.get("checksum") == checksum]

    def map_files(self, place_handle):
        """Handles of the boundary map files in a place's gallery"""
        return [r["ref"] for r in self.places[place_handle].get("media_list") or []
                if boundaries.is_boundary(self.media[r["ref"]])]


def _fake_geojson(monkeypatch, fail_for=(), geoms=None):
    fetched = []

    async def fake_fetch(osm_type, osm_id, **kw):
        fetched.append((osm_type, osm_id))
        if (osm_type, osm_id) in fail_for:
            raise boundaries.BoundaryFetchError("no polygon")
        return (geoms or {}).get("geom", GEOM)

    monkeypatch.setattr(boundaries, "fetch_geojson", fake_fetch)
    monkeypatch.setattr(boundaries.asyncio, "sleep", _no_sleep)
    return fetched


def test_map_file_is_the_migrated_sidecar_feature():
    content = boundaries.map_file(PLACE, GEOM, "relation", 62411)
    sidecar = {"type": "Feature",
               "properties": {"gramps_id": "P0001", "osm_type": "relation", "osm_id": 62411,
                              "name": "Norra Ny", "relation_id": 62411},
               "geometry": GEOM}
    migrated = {**sidecar, "properties": {**sidecar["properties"], "stroke": "#cc2a36",
                                          "stroke-width": 2, "fill": "#cc2a36", "fill-opacity": 0.22}}
    assert content == json.dumps(migrated, separators=(",", ":")).encode()
    way = json.loads(boundaries.map_file(PLACE, GEOM, "way", 99))
    assert way["properties"]["osm_type"] == "way" and "relation_id" not in way["properties"]


def test_generate_one_uploads_a_map_file_and_adds_it_to_the_gallery(monkeypatch):
    geoms = {}
    fetched = _fake_geojson(monkeypatch, geoms=geoms)
    gr = FakeGramps([{**PLACE, "media_list": [{"ref": "photo"}]}], [PHOTO])

    r1 = run(boundaries.generate_one(gr, "ph1", force=False))
    handle = r1["media_handle"]
    assert r1["written"] is True and fetched == [("relation", 62411)] and gr.uploads == [handle]
    media = gr.media[handle]
    assert media["mime"] == "application/geo+json" and media["desc"] == "OSM boundary: Norra Ny"
    assert media["attribute_list"] == [osm_attr("relation", 62411)]
    assert gr.files[handle] == boundaries.map_file(PLACE, GEOM, "relation", 62411)
    assert gr.places["ph1"]["media_list"] == [
        {"ref": "photo"},
        {"_class": "MediaRef", "ref": handle, "rect": [], "private": False,
         "attribute_list": [], "citation_list": [], "note_list": []}]

    r2 = run(boundaries.generate_one(gr, "ph1", force=False))
    assert r2 == {**r1, "written": False} and len(fetched) == 1

    r3 = run(boundaries.generate_one(gr, "ph1", force=True))
    assert r3 == {**r1, "written": False} and len(fetched) == 2  # same content: Gramps keeps the file

    geoms["geom"] = NEW_GEOM
    r4 = run(boundaries.generate_one(gr, "ph1", force=True))
    assert r4 == {**r1, "written": True} and gr.uploads == [handle]
    assert json.loads(gr.files[handle])["geometry"] == NEW_GEOM
    assert gr.map_files("ph1") == [handle] and gr.updated == ["ph1"]


def test_generate_one_requires_osm_url():
    gr = FakeGramps([{"handle": "ph2", "gramps_id": "P0002", "name": {"value": "Nowhere"}, "urls": []}])
    with pytest.raises(boundaries.BoundaryFetchError):
        run(boundaries.generate_one(gr, "ph2", force=False))


def test_generate_one_refreshes_an_outdated_map_file_in_place(monkeypatch):
    fetched = _fake_geojson(monkeypatch)
    note = {"_class": "Attribute", "type": "Source", "value": "polygons.openstreetmap.fr",
            "private": False, "citation_list": [], "note_list": []}
    gr = FakeGramps([{**PLACE, "media_list": [{"ref": "mb"}]}],
                    [map_file_media("mb", "relation", 99, attribute_list=[note, osm_attr("relation", 99)])])
    r = run(boundaries.generate_one(gr, "ph1", force=False))
    assert fetched == [("relation", 62411)]
    assert r["written"] is True and r["media_handle"] == "mb" and gr.uploads == []
    assert gr.media["mb"]["attribute_list"] == [note, osm_attr("relation", 62411)]
    assert gr.updated == []  # already in the gallery


def test_generate_one_reuses_a_map_file_an_interrupted_run_left_unattached(monkeypatch):
    _fake_geojson(monkeypatch)
    content = boundaries.map_file(PLACE, GEOM, "relation", 62411)
    orphan = {"handle": "orphan", "gramps_id": "O0009", "mime": "application/geo+json", "desc": "",
              "checksum": hashlib.md5(content).hexdigest(), "attribute_list": []}
    gr = FakeGramps([PLACE], [orphan])
    r = run(boundaries.generate_one(gr, "ph1", force=False))
    assert r["media_handle"] == "orphan" and gr.uploads == []
    assert gr.map_files("ph1") == ["orphan"]
    assert gr.media["orphan"]["desc"] == "OSM boundary: Norra Ny"

    # a copy another place shows is not taken
    other = {"handle": "ph9", "gramps_id": "P0009", "name": {"value": "Elsewhere"}, "urls": [],
             "media_list": [{"ref": "orphan"}]}
    gr = FakeGramps([PLACE, other], [orphan])
    r = run(boundaries.generate_one(gr, "ph1", force=False))
    assert gr.uploads == [r["media_handle"]] and r["media_handle"] != "orphan"


PLACE_UNLINKED = {"handle": "ph2", "gramps_id": "P0002", "name": {"value": "Nowhere"}, "urls": []}
PLACE_WAY = {"handle": "ph3", "gramps_id": "P0003", "name": {"value": "Kyrkan"},
             "urls": [{"path": "https://www.openstreetmap.org/way/77"}]}
PLACE_PARENT = {"handle": "ph-mn", "gramps_id": "P0100", "name": {"value": "Minnesota"}, "urls": []}
PLACE_CHILD = {"handle": "ph-hc", "gramps_id": "P0101", "name": {"value": "Hennepin County"},
               "urls": [], "placeref_list": [{"ref": "ph-mn"}]}


def test_listing_reads_every_boundary_from_one_media_listing():
    gr = FakeGramps(
        [{**PLACE, "media_list": [{"ref": "photo"}, {"ref": "mb"}]},
         {**PLACE_WAY, "media_list": [{"ref": "mw"}]},
         {**PLACE_CHILD, "media_list": [{"ref": "plain"}]},
         {**PLACE_PARENT, "urls": [{"path": "https://www.openstreetmap.org/relation/165471"}],
          "media_list": [{"ref": "jpeg"}]}],
        [PHOTO, map_file_media("mb", "relation", 99), map_file_media("mw", "way", 77),
         {"handle": "plain", "mime": "application/geo+json", "attribute_list": []},
         {"handle": "jpeg", "mime": "image/jpeg", "attribute_list": [osm_attr("relation", 165471)]}])
    rows = {r["gramps_id"]: r for r in run(boundaries.listing(gr))}
    assert gr.media_listings == ["handle,mime,attribute_list"]
    assert rows["P0101"]["hierarchy"] == ["Hennepin County", "Minnesota"]
    assert rows["P0001"]["has_boundary"] and rows["P0001"]["boundary_osm"] == ("relation", 99)
    assert boundaries.outdated(rows["P0001"])
    assert rows["P0003"]["has_boundary"] and not boundaries.outdated(rows["P0003"])
    assert not rows["P0101"]["has_boundary"]  # a GeoJSON file without an OSM URL is someone else's map
    assert not rows["P0100"]["has_boundary"]  # only GeoJSON counts

    gr.media_listings.clear()
    rows = run(boundaries.listing(gr, with_boundaries=False))
    assert gr.media_listings == [] and not any(r["has_boundary"] for r in rows)


def test_boundary_scan_lists_linked_places_without_a_current_map_file():
    gr = FakeGramps([PLACE, PLACE_UNLINKED, {**PLACE_WAY, "media_list": [{"ref": "mw"}]}],
                    [map_file_media("mw", "way", 77)])
    events = _events(boundaries.scan(gr))
    rows = [e for e in events if e.kind == "item"]
    assert [(e.entity, e.source_id, e.gramps_id, e.action) for e in rows] == [
        ("place", "ph1", "P0001", "would_create")]
    assert rows[0].title == "Norra Ny" and rows[0].data["cols"] == {"osm": "relation 62411"}
    assert events[-1].data == {"generated": 1, "errors": 0}


def test_generate_missing_honours_selection_and_reports_progress(monkeypatch):
    fetched = _fake_geojson(monkeypatch)
    gr = FakeGramps([PLACE, PLACE_UNLINKED, PLACE_WAY])
    events = _events(boundaries.generate_missing(gr, selected={"place:ph3"}))
    assert fetched == [("way", 77)]
    rows = [e for e in events if e.kind == "item"]
    assert [(e.source_id, e.action) for e in rows] == [("ph3", "created")]
    progress = [e.data for e in events if e.kind == "progress"]
    assert [d["done"] for d in progress] == [0, 1] and {d["total"] for d in progress} == {1}
    assert len(gr.map_files("ph3")) == 1 and not gr.places["ph1"].get("media_list")


def test_boundary_scan_flags_an_outdated_map_file_and_regenerates_it(monkeypatch):
    fetched = _fake_geojson(monkeypatch)
    gr = FakeGramps([{**PLACE, "media_list": [{"ref": "mb"}]}], [map_file_media("mb", "relation", 99)])
    rows = [e for e in _events(boundaries.scan(gr)) if e.kind == "item"]
    assert [(e.gramps_id, e.action) for e in rows] == [("P0001", "would_update")]
    assert rows[0].data["cols"] == {"osm": "relation 62411", "boundary": "map file of relation 99"}
    events = _events(boundaries.generate_missing(gr, selected={"place:ph1"}))
    assert fetched == [("relation", 62411)]
    assert [e.action for e in events if e.kind == "item"] == ["updated"]
    assert gr.uploads == [] and boundaries.boundary_osm(gr.media["mb"]) == ("relation", 62411)
    assert [e for e in _events(boundaries.scan(gr)) if e.kind == "item"] == []


def test_generate_missing_skips_a_forced_boundary_whose_content_is_unchanged(monkeypatch):
    _fake_geojson(monkeypatch)
    gr = FakeGramps([PLACE])
    run(boundaries.generate_one(gr, "ph1", force=False))
    events = _events(boundaries.generate_missing(gr, force=True))
    assert [(e.action, e.detail) for e in events if e.kind == "item"] == [("skipped", "boundary unchanged")]
    assert events[-1].data == {"generated": 0, "errors": 0}


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


def test_link_scan_suggests_links_and_coordinates(monkeypatch):
    searches, lookups = _fake_osm(monkeypatch)
    fetched = _fake_geojson(monkeypatch)
    gr = FakeGramps([PLACE, PLACE_PARENT, PLACE_CHILD, PLACE_LOCATED, PLACE_FARM])
    suggestions = {}
    events = _events(boundaries.scan_links(gr, suggestions))
    rows = {e.gramps_id: e for e in events if e.kind == "item"}
    assert lookups == [("relation", 62411)]
    assert sorted(searches) == ["Center City, Minnesota", "Hennepin County, Minnesota",
                                "Lindqvist farm, Minnesota", "Minnesota"]
    assert rows["P0101"].action == "would_create"
    assert rows["P0101"].data["cols"] == {"osm": "relation 1795848", "coordinates": "45.0000, -93.4000",
                                          "boundary": "fetch",
                                          "match": "Hennepin County, Minnesota, United States"}
    assert rows["P0102"].action == "would_create"
    assert set(rows["P0102"].data["cols"]) == {"osm", "boundary", "match"}
    assert rows["P0103"].action == "would_update"
    assert set(rows["P0103"].data["cols"]) == {"coordinates", "match"}
    assert rows["P0001"].action == "would_update"
    assert rows["P0001"].data["cols"]["coordinates"] == "60.5000, 13.2000"
    assert rows["P0001"].data["cols"]["boundary"] == "fetch"
    assert "P0100" not in rows
    assert events[-1].data == {"linked": 2, "located": 3, "unmatched": 1, "errors": 0}
    assert set(suggestions) == {"ph-hc", "ph-cc", "ph-farm", "ph1"}

    events = _events(boundaries.apply_links(
        gr, {"place:ph-hc", "place:ph-cc", "place:ph-farm", "place:ph1"}, suggestions))
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
    assert sorted(fetched) == [("relation", 62411), ("relation", 137256), ("relation", 1795848)]
    assert {h for h in gr.places if gr.map_files(h)} == {"ph1", "ph-hc", "ph-cc"}
    assert boundaries.boundary_osm(gr.media[gr.map_files("ph-cc")[0]]) == ("relation", 137256)
    cols = {e.gramps_id: e.data["cols"] for e in events if e.kind == "item"}
    assert cols["P0101"]["boundary"] == "written" and "boundary" not in cols["P0103"]
    assert events[-1].data == {"linked": 2, "located": 3, "generated": 3, "errors": 0}


def test_link_apply_keeps_the_link_when_the_boundary_fails(monkeypatch):
    _fake_osm(monkeypatch)
    _fake_geojson(monkeypatch, fail_for={("relation", 1795848)})
    gr = FakeGramps([PLACE_PARENT, PLACE_CHILD])
    suggestions = {}
    _events(boundaries.scan_links(gr, suggestions))
    events = _events(boundaries.apply_links(gr, {"place:ph-hc"}, suggestions))
    row = [e for e in events if e.kind == "item"][0]
    assert row.action == "created"
    assert row.data["cols"]["boundary"] == "failed: no polygon"
    assert boundaries.osm_ref(gr.places["ph-hc"]) == ("relation", 1795848)
    assert gr.uploads == [] and gr.map_files("ph-hc") == []
    assert events[-1].data == {"linked": 1, "located": 1, "generated": 0, "errors": 1}


def _app(gramps):
    app = FastAPI()
    app.include_router(places_routes.router)
    app.state.gramps = gramps
    app.state.cfg = SimpleNamespace()  # boundaries need no config
    app.state.caches = {}
    return app


def _call(app, method, url, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bifrost") as c:
            return await c.request(method, url, **kw)
    return asyncio.run(go())


def test_linking_a_place_by_hand_adds_its_boundary_map_file(monkeypatch):
    _fake_osm(monkeypatch)
    fetched = _fake_geojson(monkeypatch)
    gr = FakeGramps([PLACE_PARENT, PLACE_CHILD])
    app = _app(gr)
    assert _call(app, "GET", "/places/api/config").json() == {"enabled": True}
    r = _call(app, "POST", "/places/api/set-relation", json={"gramps_id": "p0101", "relation": "1795848"})
    assert r.status_code == 200 and r.json()["boundary_error"] is None
    assert fetched == [("relation", 1795848)]
    assert boundaries.osm_ref(gr.places["ph-hc"]) == ("relation", 1795848)
    assert boundaries.boundary_osm(gr.media[gr.map_files("ph-hc")[0]]) == ("relation", 1795848)
