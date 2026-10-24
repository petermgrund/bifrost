"""Read-only API v1: codes, export"""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core import db
from bifrost.core.config import SyncPaperlessConfig
from bifrost.modules import codes, faces, photo_collections
from bifrost.web.routes import api as routes


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


class Gramps:
    def __init__(self, media=None, down=False):
        self.media, self.down = media or {}, down

    def _check(self):
        if self.down:
            raise httpx.ConnectError("gramps is down")

    async def get_media_by_gramps_id(self, gramps_id):
        self._check()
        return {"gramps_id": gramps_id, "desc": self.media[gramps_id]} if gramps_id in self.media else None

    async def media_descriptions(self):
        self._check()
        return dict(self.media)


def app_for(conn, gramps=None):
    app = FastAPI()
    app.include_router(routes.router)
    app.state.conn = conn
    app.state.gramps = gramps or Gramps()
    app.state.cfg = SimpleNamespace(
        sync_paperless=SyncPaperlessConfig(gramps_id_field_id=3, public_url="http://paperless",
                                           gramps_public_url="http://gramps"),
        sync_immich=SimpleNamespace(gramps_public_url="", public_url="http://immich"))
    return app


def get(app, url):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bifrost") as c:
            return await c.get(url)
    return asyncio.run(go())


@pytest.fixture
def ledger(conn):
    album = codes.claim(conn, "R7KM3D", kind="group", note="Berg album", location="B2.C3")
    codes.claim(conn, "W9TP4F", kind="item", note="Loose print", parent=album)
    codes.add_instance(conn, album, "https://example.org/album")
    with conn:
        conn.execute("INSERT INTO scan_register (scan_no, object_id) VALUES ('a000277', 'R7KM3D')")
    return conn


class TestCode:
    def test_a_ledger_entry(self, ledger):
        r = get(app_for(ledger, gramps=Gramps(media={"R7KM3D": "Berg family album"})), "/api/v1/code/r7km-3d")
        assert r.status_code == 200
        body = r.json()
        assert (body["code"], body["status"], body["kind"], body["description"]) == (
            "R7KM3D", "in use", "group", "Berg album")
        assert (body["title"], body["location"], body["children"], body["scans"]) == (
            "Berg family album", "B2.C3", ["W9TP4F"], ["a000277"])
        assert body["withdrawn"] is None
        assert {"where": "Link", "text": "https://example.org/album", "url": "https://example.org/album"} in body["instances"]
        assert {"attention", "deletable", "in_ledger", "pencilings"}.isdisjoint(body)

    def test_status_rests_on_the_ledger_when_gramps_is_down(self, ledger):
        body = get(app_for(ledger, gramps=Gramps(down=True)), "/api/v1/code/W9TP4F").json()
        assert (body["status"], body["parent"]) == ("reserved", "R7KM3D")

    def test_codes_only_in_gramps_are_not_bifrost_data(self, ledger):
        r = get(app_for(ledger, gramps=Gramps(media={"X4FG7H": "Scan"})), "/api/v1/code/X4FG7H")
        assert r.status_code == 404 and r.json()["detail"] == "X4FG7H isn't in Bifrost's ledger"


def test_export(ledger):
    cid = photo_collections.create(ledger, "Portraits")["id"]
    photo_collections.add_items(ledger, cid, ["asset-1", "asset-2"])
    faces.set_link(ledger, "H_ANDERS", "imm-person-1", label="Anders")
    ledger.executemany("INSERT INTO photo_links (asset_id, url, added_at) VALUES (?, ?, 't')",
                       [("asset-2", "https://example.org/album/2"), ("asset-1", "https://example.org/album/1")])
    ledger.commit()
    r = get(app_for(ledger, gramps=Gramps(media={"R7KM3D": "Album"})), "/api/v1/export")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="bifrost-export-')
    body = r.json()
    assert body["api"] == "v1"
    by_code = {c["code"]: c for c in body["codes"]}
    assert (by_code["R7KM3D"]["status"], by_code["W9TP4F"]["status"]) == ("in use", "reserved")
    assert body["collections"][0]["name"] == "Portraits"
    assert [s["asset_id"] for s in body["collections"][0]["slots"]] == ["asset-1", "asset-2"]
    assert body["person_links"][0]["immich_person_id"] == "imm-person-1"
    assert [(p["asset_id"], [x["url"] for x in p["links"]]) for p in body["photo_links"]] == [
        ("asset-1", ["https://example.org/album/1"]), ("asset-2", ["https://example.org/album/2"])]
    assert body["photo_links"][0]["links"][0]["added_at"]
    assert set(body) == {"api", "exported_at", "codes", "collections", "photo_links", "person_links"}


def test_export_without_gramps(ledger):
    body = get(app_for(ledger, gramps=Gramps(down=True)), "/api/v1/export").json()
    by_code = {c["code"]: c for c in body["codes"]}
    assert (by_code["R7KM3D"]["status"], by_code["W9TP4F"]["status"]) == ("reserved", "reserved")
    json.dumps(body)
