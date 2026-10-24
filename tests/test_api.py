"""Read-only API v1: codes, export"""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core import db
from bifrost.core.config import SyncPaperlessConfig
from bifrost.modules import codes, photo_collections
from bifrost.web.routes import api as routes

CODE_KEYS = {"code", "status", "type", "title", "created", "minted", "withdrawn", "supersedes", "history"}


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
    codes.claim(conn, "R7KM3D")
    codes.claim(conn, "W9TP4F")
    codes.claim(conn, "X2BR7N")
    codes.withdraw(conn, "X2BR7N", "penciled on the wrong print", superseded_by="R7KM3D")
    return conn


class TestCode:
    def test_a_ledger_entry(self, ledger):
        r = get(app_for(ledger, gramps=Gramps(media={"R7KM3D": "Berg family album"})), "/api/v1/code/r7km-3d")
        assert r.status_code == 200
        body = r.json()
        assert set(body) == CODE_KEYS
        assert (body["code"], body["status"], body["title"], body["type"]) == (
            "R7KM3D", "in use", "Berg family album", None)
        assert body["withdrawn"] is None and body["supersedes"] == ["X2BR7N"]
        assert [e["what"] for e in body["history"]] == ["Created"] and body["created"] and body["minted"] is None

    def test_a_withdrawn_entry(self, ledger):
        body = get(app_for(ledger), "/api/v1/code/X2BR7N").json()
        assert body["status"] == "withdrawn" and body["supersedes"] == []
        assert body["withdrawn"] == {"at": body["history"][-1]["at"], "reason": "penciled on the wrong print",
                                     "superseded_by": "R7KM3D"}

    def test_status_rests_on_the_ledger_when_gramps_is_down(self, ledger):
        body = get(app_for(ledger, gramps=Gramps(down=True)), "/api/v1/code/W9TP4F").json()
        assert (body["status"], body["title"]) == ("reserved", None)

    def test_codes_only_in_gramps_are_not_bifrost_data(self, ledger):
        r = get(app_for(ledger, gramps=Gramps(media={"X4FG7H": "Scan"})), "/api/v1/code/X4FG7H")
        assert r.status_code == 404 and r.json()["detail"] == "X4FG7H isn't in Bifrost's ledger"
        assert get(app_for(ledger), "/api/v1/code/-").status_code == 404


def test_export(ledger):
    cid = photo_collections.create(ledger, "Portraits")["id"]
    photo_collections.add_items(ledger, cid, ["asset-1", "asset-2"])
    ledger.execute("INSERT INTO person_links (gramps_handle, immich_person_id, created_at) VALUES ('H1', 'p1', 't')")
    ledger.executemany("INSERT INTO photo_links (asset_id, url, added_at) VALUES (?, ?, 't')",
                       [("asset-2", "https://example.org/album/2"), ("asset-1", "https://example.org/album/1")])
    ledger.commit()
    r = get(app_for(ledger, gramps=Gramps(media={"R7KM3D": "Album"})), "/api/v1/export")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="bifrost-export-')
    body = r.json()
    assert set(body) == {"api", "exported_at", "codes", "collections", "photo_links"}
    assert body["api"] == "v1"
    by_code = {c["code"]: c for c in body["codes"]}
    assert set(by_code) == {"R7KM3D", "W9TP4F", "X2BR7N"} | {"C8T5", "J82D", "JYMZ", "6H2P", "G8NQ"}
    assert all(set(c) == CODE_KEYS for c in body["codes"])
    assert (by_code["R7KM3D"]["status"], by_code["W9TP4F"]["status"], by_code["X2BR7N"]["status"]) == (
        "in use", "reserved", "withdrawn")
    assert by_code["X2BR7N"]["withdrawn"]["superseded_by"] == "R7KM3D"
    assert body["collections"][0]["name"] == "Portraits"
    assert [s["asset_id"] for s in body["collections"][0]["slots"]] == ["asset-1", "asset-2"]
    assert [(p["asset_id"], [x["url"] for x in p["links"]]) for p in body["photo_links"]] == [
        ("asset-1", ["https://example.org/album/1"]), ("asset-2", ["https://example.org/album/2"])]
    assert body["photo_links"][0]["links"][0]["added_at"]


def test_export_without_gramps(ledger):
    body = get(app_for(ledger, gramps=Gramps(down=True)), "/api/v1/export").json()
    by_code = {c["code"]: c for c in body["codes"]}
    assert (by_code["R7KM3D"]["status"], by_code["W9TP4F"]["status"]) == ("reserved", "reserved")
    json.dumps(body)
