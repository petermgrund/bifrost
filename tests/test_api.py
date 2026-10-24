"""Read-only API v1: pinpoints, PIDs, codes, export"""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core import db
from bifrost.core.config import SyncPaperlessConfig
from bifrost.modules import codes, faces, photo_collections, tables
from bifrost.web.routes import api as routes


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


def census(**kw):
    g = {
        "frame": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]],
        "cols": [{"id": "name", "name": "Name", "person": True, "u": [0, 0]},
                 {"id": "rel", "name": "Relation", "trans": "Relation (en)", "u": [0.5, 0.5]},
                 {"id": "age", "name": "Age", "no": 12, "u": [0.75, 0.75]}],
        "rows": [{"id": f"r{j}", "v": [j / 4, j / 4]} for j in range(4)],
        "first_line": 51,
        "group_col": "name",
        "cells": {"r0": {"name": "Anders", "rel": "Husbonde", "age": "34"}, "r1": {"name": "Maria"}},
        "trans": {"r0": {"rel": "Head"}},
        "people": {"r0": {"name": "H_ANDERS"}, "r1": {"name": "H_GONE"}},
    }
    g.update(kw)
    return tables.normalize_grid(g)


class Paperless:
    def __init__(self, docs, down=False):
        self.docs, self.down = docs, down

    async def documents_with_value(self, field_id, value):
        return [d for d, pid in self.docs.items() if pid == value]

    async def custom_field_values(self, field_id, ids=None):
        if self.down:
            raise httpx.ConnectError("paperless is down")
        return {d: pid for d, pid in self.docs.items() if ids is None or d in ids}


class Gramps:
    def __init__(self, people=None, media=None, down=False):
        self.people, self.media, self.down = people or {}, media or {}, down

    def _check(self):
        if self.down:
            raise httpx.ConnectError("gramps is down")

    async def person_profile(self, handle):
        self._check()
        p = self.people.get(handle)
        return {"handle": handle, "gramps_id": p[0], "profile": {"name_given": p[1]}} if p else None

    async def get_media_by_gramps_id(self, gramps_id):
        self._check()
        return {"gramps_id": gramps_id, "desc": self.media[gramps_id]} if gramps_id in self.media else None

    async def media_descriptions(self):
        self._check()
        return dict(self.media)


def app_for(conn, paperless=None, gramps=None):
    app = FastAPI()
    app.include_router(routes.router)
    app.state.conn = conn
    app.state.paperless = paperless or Paperless({8: "69T5AU"})
    app.state.gramps = gramps or Gramps({"H_ANDERS": ("I0007", "Anders")})
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
def saved(conn):
    tables.save_table(conn, 8, 1, census(), 0, "1910 census, Center City")
    tables.add_note(conn, 8, 1, 0.5, 0.1, "Enumerator: J. Berg")
    tables.add_note(conn, 8, 2, 0.2, 0.3, "Back of the sheet")
    return conn


class TestPinpoint:
    def test_a_cell(self, saved):
        r = get(app_for(saved), "/api/v1/pinpoint/69t5au.p1.l51.c2")
        assert r.status_code == 200
        body = r.json()
        assert (body["pinpoint"], body["pid"], body["paperless_id"], body["page"]) == ("69T5AU.L51.C2", "69T5AU", 8, 1)
        assert body["title"] == "1910 census, Center City"
        assert body["column"] == {"no": 2, "name": "Relation", "translation": "Relation (en)",
                                  "person_column": False, "household": False}
        assert body["lines"] == [{"line": 51, "pinpoint": "69T5AU.L51.C2", "cells": [
            {"column": 2, "name": "Relation", "value": "Husbonde", "translation": "Head", "person": None}]}]
        assert body["region"]["box"] == [0.5, 0.2, 0.7, 0.35]
        assert body["links"] == {"bifrost": "http://bifrost/tables/8?page=1#L51.C2",
                                 "pid": "http://bifrost/api/v1/pid/69T5AU"}

    def test_a_household_with_people(self, saved):
        body = get(app_for(saved), "/api/v1/pinpoint/69T5AU.L51-52").json()
        assert body["column"] is None and [ln["pinpoint"] for ln in body["lines"]] == ["69T5AU.L51", "69T5AU.L52"]
        first, second = (ln["cells"] for ln in body["lines"])
        assert [c["column"] for c in first] == [1, 2, 12]
        assert first[0]["person"] == {"handle": "H_ANDERS", "gramps_id": "I0007", "name": "Anders"}
        assert second == [{"column": 1, "name": "Name", "value": "Maria", "translation": None,
                           "person": {"handle": "H_GONE", "missing": True}}]
        assert body["region"]["corners"] == [[0.1, 0.2], [0.9, 0.2], [0.9, 0.5], [0.1, 0.5]]

    def test_printed_column_numbers_and_whole_columns(self, saved):
        body = get(app_for(saved), "/api/v1/pinpoint/69T5AU.C12").json()
        assert body["column"]["name"] == "Age"
        assert [ln["pinpoint"] for ln in body["lines"]] == [f"69T5AU.L{n}.C12" for n in range(51, 55)]
        assert [ln["cells"] for ln in body["lines"]][0] == [
            {"column": 12, "name": "Age", "value": "34", "translation": None, "person": None}]
        assert get(app_for(saved), "/api/v1/pinpoint/69T5AU.C3").status_code == 404

    def test_a_note(self, saved):
        r = get(app_for(saved), "/api/v1/pinpoint/69t5au.n2")
        assert r.status_code == 200
        body = r.json()
        assert (body["pinpoint"], body["pid"], body["paperless_id"], body["page"]) == ("69T5AU.N2", "69T5AU", 8, 2)
        assert body["title"] == "1910 census, Center City"
        assert body["note"] == {**body["note"], "no": 2, "x": 0.2, "y": 0.3, "text": "Back of the sheet"}
        assert set(body["note"]) == {"no", "x", "y", "text", "created_at", "updated_at"}
        assert body["region"] == {"box": [0.2, 0.3, 0.2, 0.3], "corners": [[0.2, 0.3]] * 4}
        assert "lines" not in body and "column" not in body
        assert body["links"] == {"bifrost": "http://bifrost/tables/8?page=2#N2",
                                 "pid": "http://bifrost/api/v1/pid/69T5AU"}

    def test_people_stay_handles_when_gramps_is_down(self, saved):
        body = get(app_for(saved, gramps=Gramps(down=True)), "/api/v1/pinpoint/69T5AU.L51.C1").json()
        assert body["lines"][0]["cells"][0]["person"] == {"handle": "H_ANDERS"}

    @pytest.mark.parametrize("url,detail", [
        ("/api/v1/pinpoint/69T5AU.X1", "'69T5AU.X1' is not a pinpoint"),
        ("/api/v1/pinpoint/ZZZZZZ.L1", "no Paperless document has the PID ZZZZZZ"),
        ("/api/v1/pinpoint/69T5AU.P3.L1", "69T5AU has no table on page 3"),
        ("/api/v1/pinpoint/69T5AU.L53-55", "line 55 isn't in the table on page 1 (lines 51-54)"),
        ("/api/v1/pinpoint/69T5AU.L51.C9", "column 9 isn't in the table on page 1"),
        ("/api/v1/pinpoint/69T5AU.N9", "69T5AU has no note 9"),
        ("/api/v1/pinpoint/69T5AU.P2.N1", "'69T5AU.P2.N1' is not a pinpoint"),
    ])
    def test_misses(self, saved, url, detail):
        r = get(app_for(saved), url)
        assert r.status_code == 404 and r.json()["detail"] == detail


class TestOpen:
    def app(self, conn):
        from bifrost.web.routes import tables as tables_routes
        app = app_for(conn)
        app.include_router(tables_routes.router)
        return app

    @pytest.mark.parametrize("pinpoint,target", [
        ("69t5au.l52.c12", "/tables/8?page=1#L52.C12"),
        ("69T5AU.P2", "/tables/8?page=2"),
        ("69T5AU.N2", "/tables/8?page=2#N2"),
    ])
    def test_a_pinpoint_opens_its_page(self, saved, pinpoint, target):
        r = get(self.app(saved), f"/tables/at/{pinpoint}")
        assert (r.status_code, r.headers["location"]) == (302, target)

    @pytest.mark.parametrize("pinpoint,detail", [
        ("69T5AU.N9", "69T5AU has no note 9"),
        ("ZZZZZZ.N1", "no Paperless document has the PID ZZZZZZ"),
        ("69T5AU.N0", "'69T5AU.N0' is not a pinpoint"),
    ])
    def test_misses(self, saved, pinpoint, detail):
        r = get(self.app(saved), f"/tables/at/{pinpoint}")
        assert r.status_code == 404 and r.json()["detail"] == detail


class TestPid:
    def test_tables_and_notes_by_page(self, saved):
        body = get(app_for(saved), "/api/v1/pid/69t5-au").json()
        assert (body["pid"], body["paperless_id"], body["translations"]) == ("69T5AU", 8, True)
        one, two = body["pages"]
        assert one["notes"][0]["text"] == "Enumerator: J. Berg" and set(one["notes"][0]) == {
            "no", "pinpoint", "x", "y", "text", "created_at", "updated_at"}
        assert (one["notes"][0]["no"], one["notes"][0]["pinpoint"]) == (1, "69T5AU.N1")
        assert [c["name"] for c in one["table"]["columns"]] == ["Name", "Relation", "Age"]
        assert one["table"]["columns"][0]["household"] and one["table"]["columns"][0]["person_column"]
        assert [ln["line"] for ln in one["table"]["lines"]] == [51, 52, 53, 54]
        assert one["table"]["lines"][2] == {"line": 53, "pinpoint": "69T5AU.L53", "cells": []}
        assert one["table"]["lines"][0]["cells"][0]["person"]["gramps_id"] == "I0007"
        assert one["table"]["layout"]["lines"][1] == [0.25, 0.25]
        assert two == {"page": 2, "table": None, "notes": [{**two["notes"][0], "no": 2, "pinpoint": "69T5AU.N2",
                                                              "text": "Back of the sheet"}]}
        assert body["links"] == {"bifrost": "http://bifrost/tables/8",
                                 "paperless": "http://paperless/documents/8/details",
                                 "gramps": "http://gramps/media/69T5AU",
                                 "code": "http://bifrost/api/v1/code/69T5AU"}

    def test_later_pages_carry_p_in_their_pinpoints(self, saved):
        tables.save_table(saved, 8, 2, census(), 0)
        pages = get(app_for(saved), "/api/v1/pid/69T5AU").json()["pages"]
        assert pages[1]["table"]["lines"][0]["pinpoint"] == "69T5AU.P2.L51"

    def test_unknown(self, saved):
        r = get(app_for(saved), "/api/v1/pid/ZZZZZZ")
        assert r.status_code == 404 and r.json()["detail"] == "no Paperless document has the PID ZZZZZZ"


@pytest.fixture
def ledger(conn):
    album = codes.claim(conn, "R7KM3D", kind="group", note="Berg album", location="B2.C3")
    codes.claim(conn, "W9TP4F", kind="item", note="Loose print", parent=album)
    codes.mark_penciled(conn, album)
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
        assert len(body["pencilings"]) == 1 and body["withdrawn"] is None
        assert {"where": "Link", "text": "https://example.org/album", "url": "https://example.org/album"} in body["instances"]
        assert {"attention", "deletable", "in_ledger"}.isdisjoint(body)

    def test_status_rests_on_the_ledger_when_gramps_is_down(self, ledger):
        body = get(app_for(ledger, gramps=Gramps(down=True)), "/api/v1/code/W9TP4F").json()
        assert (body["status"], body["parent"]) == ("reserved", "R7KM3D")

    def test_codes_only_in_gramps_are_not_bifrost_data(self, ledger):
        r = get(app_for(ledger, gramps=Gramps(media={"X4FG7H": "Scan"})), "/api/v1/code/X4FG7H")
        assert r.status_code == 404 and r.json()["detail"] == "X4FG7H isn't in Bifrost's ledger"


def test_export(saved, ledger):
    cid = photo_collections.create(saved, "Portraits")["id"]
    photo_collections.add_items(saved, cid, ["asset-1", "asset-2"])
    faces.set_link(saved, "H_ANDERS", "imm-person-1", label="Anders")
    saved.executemany("INSERT INTO photo_links (asset_id, url, added_at) VALUES (?, ?, 't')",
                      [("asset-2", "https://example.org/album/2"), ("asset-1", "https://example.org/album/1")])
    saved.commit()
    tables.save_table(saved, 11, 1, census(), 0, "Unsynced page")
    app = app_for(saved, paperless=Paperless({8: "69t5au", 11: None}),
                  gramps=Gramps({"H_ANDERS": ("I0007", "Anders")}, media={"R7KM3D": "Album"}))
    r = get(app, "/api/v1/export")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="bifrost-export-')
    body = r.json()
    assert body["api"] == "v1"
    assert [(d["paperless_id"], d["pid"]) for d in body["documents"]] == [(8, "69T5AU"), (11, None)]
    assert body["documents"][0]["pages"][0]["table"]["lines"][0]["cells"][0]["person"] == {"handle": "H_ANDERS"}
    assert body["documents"][1]["pages"][0]["table"]["lines"][0]["pinpoint"] is None
    by_code = {c["code"]: c for c in body["codes"]}
    assert (by_code["R7KM3D"]["status"], by_code["W9TP4F"]["status"]) == ("in use", "reserved")
    assert body["collections"][0]["name"] == "Portraits"
    assert [s["asset_id"] for s in body["collections"][0]["slots"]] == ["asset-1", "asset-2"]
    assert body["person_links"][0]["immich_person_id"] == "imm-person-1"
    assert [(p["asset_id"], [x["url"] for x in p["links"]]) for p in body["photo_links"]] == [
        ("asset-1", ["https://example.org/album/1"]), ("asset-2", ["https://example.org/album/2"])]
    assert body["photo_links"][0]["links"][0]["added_at"]
    assert set(body) == {"api", "exported_at", "documents", "codes", "collections", "photo_links", "person_links"}


def test_export_without_paperless_or_gramps(saved, ledger):
    app = app_for(saved, paperless=Paperless({8: "69T5AU"}, down=True), gramps=Gramps(down=True))
    body = get(app, "/api/v1/export").json()
    assert body["documents"][0]["pid"] is None
    by_code = {c["code"]: c for c in body["codes"]}
    assert (by_code["R7KM3D"]["status"], by_code["W9TP4F"]["status"]) == ("penciled", "reserved")
    json.dumps(body)
