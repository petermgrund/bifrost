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
