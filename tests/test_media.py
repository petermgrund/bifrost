"""The media list, hand-written codes, and deleting and merging media"""

import asyncio
import copy
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core.clients.gramps import GrampsError
from bifrost.core.config import GrampsConfig, SyncImmichConfig, SyncPaperlessConfig
from bifrost.modules import codes, sync_immich
from bifrost.web.routes import media as media_routes

from test_sync_immich import FakeImmich, asset

DOC_TAG = 1


def attr(name, value):
    return {"type": name, "value": value}


def media(gid, desc="A letter", change=1_792_000_000, mime="application/pdf", attrs=(), notes=()):
    return {"gramps_id": gid, "handle": f"h-{gid}", "desc": desc, "change": change, "mime": mime,
            "attribute_list": list(attrs), "note_list": list(notes)}


class FakeGramps:
    def __init__(self, media=None, notes=None, holders=None, down=False):
        self.media = media or {}
        self.notes = notes or {}
        self.holders = holders or {}
        self.down = down
        self.deleted_notes = []

    def _check(self):
        if self.down:
            raise GrampsError("GET /media/ → 502")

    async def list_media(self, keys=None):
        self._check()
        return list(self.media.values())

    async def get_media_by_gramps_id(self, gid, backlinks=False, notes=False):
        self._check()
        found = self.media.get(gid)
        if found is None:
            return None
        found = copy.deepcopy(found)
        if backlinks:
            found["backlinks"] = {"person": [h for h, o in self.holders.items()
                                             if any(r["ref"] == found["handle"] for r in o["media_list"])]}
        if notes:
            found["extended"] = {"notes": [self.notes[h] for h in found["note_list"] if h in self.notes]}
        return found

    async def delete_media(self, handle):
        self._check()
        for gid in [g for g, m in self.media.items() if m["handle"] == handle]:
            del self.media[gid]
        for obj in self.holders.values():
            obj["media_list"] = [r for r in obj["media_list"] if r["ref"] != handle]

    async def update_media(self, handle, obj):
        self.media[obj["gramps_id"]] = obj

    async def delete_note(self, handle):
        self.deleted_notes.append(handle)
        self.notes.pop(handle, None)

    async def get_object(self, api_path, handle):
        return copy.deepcopy(self.holders[handle])

    async def update_object(self, api_path, handle, obj):
        self.holders[handle] = obj

    async def media_thumbnail(self, handle, size=64):
        return b"png", "image/png"


class FakePaperless:
    def __init__(self, docs=(), down=False):
        self.docs = {d["id"]: d for d in docs}
        self.down = down

    async def document_ids(self):
        if self.down:
            raise RuntimeError("paperless down")
        return set(self.docs)

    async def get_document(self, doc_id):
        if self.down:
            raise RuntimeError("paperless down")
        return copy.deepcopy(self.docs[doc_id])

    async def resolve_tag_id(self, name):
        return {"sync": DOC_TAG}.get(name)

    async def patch_custom_fields(self, doc_id, cfs):
        self.docs[doc_id]["custom_fields"] = cfs

    async def patch_tags(self, doc_id, tags):
        self.docs[doc_id]["tags"] = tags


def document(doc_id, gid):
    return {"id": doc_id, "tags": [DOC_TAG, 9],
            "custom_fields": [{"field": 12, "value": gid}, {"field": 14, "value": f"https://g/media/{gid}"},
                              {"field": 20, "value": "kept"}]}


# ---- hand-written codes

def test_check_code_normalizes_a_hand_written_code():
    assert codes.check_code(" phkn-3d ", set()) == "PHKN3D"


@pytest.mark.parametrize("raw,status,msg", [
    ("", 400, "Type the code"),
    ("ABCDEI", 400, "contains I"),
    ("ABC23", 400, "has 5 characters"),
    ("234567", 400, "all digits"),
    ("README", 400, "reserved word"),
    ("QVWX22", 409, "already the ID of a Gramps media"),
    ("PPRK22", 409, "Paperless document 12, 13"),
])
def test_check_code_refusals(raw, status, msg):
    with pytest.raises(codes.CodeError) as exc:
        codes.check_code(raw, {"QVWX22"}, {"PPRK22": [12, 13]})
    assert exc.value.status == status and msg in exc.value.detail


def test_new_id_is_a_code_or_the_next_gramps_number(script_ids):
    script_ids("TAKEN2", "FRESH2")
    taken = {"TAKEN2", "O0003", "O0011"}
    assert codes.new_id(True, taken) == "FRESH2"
    assert codes.new_id(False, taken) == "O0012" and codes.new_id(False, taken) == "O0013"


# ---- the list

URLS = codes.Urls(gramps="https://g", paperless="https://p", immich="https://i")


def listing(**kw):
    all_media = [
        media("PPRK22", attrs=[attr("Paperless URL", "u"), attr("Paperless ID", "7")], change=1_792_000_100),
        {**media("GQNE22", attrs=[attr("Paperless ID", "8")], change=1_792_000_050),
         "date": {"dateval": [0, 6, 1923, False], "modifier": 3, "quality": 0, "text": ""}},
        media("MMGG22", desc="Farm", mime="image/jpeg", change=1_792_000_200,
              attrs=[attr("Immich ID", "a1"), attr("Merged Gramps ID", "OLD222")]),
        media("O0042", desc="Numbered", attrs=[attr("Paperless ID", "9")], change=1_792_000_000),
        media("O0001", desc="not from Bifrost", attrs=[]),
        media("PXAWN2", desc="hand-made", mime="image/png", attrs=[]),
    ]
    return codes.rows(all_media, URLS, **kw)


def test_rows_cover_the_media_that_came_from_a_source():
    rows = {r["code"]: r for r in listing(documents={"7", "9"})}
    assert set(rows) == {"PPRK22", "GQNE22", "MMGG22", "O0042"}
    assert (rows["PPRK22"]["type"], rows["PPRK22"]["title"]) == ("document", "A letter")
    assert rows["PPRK22"]["paperless"] == [{"id": "7", "url": "https://p/documents/7/details"}]
    assert rows["PPRK22"]["gramps_url"] == "https://g/media/PPRK22"
    assert rows["MMGG22"]["immich"] == [{"id": "a1", "url": "https://i/photos/a1"}] and rows["MMGG22"]["type"] == "image"
    assert rows["MMGG22"]["merged"] == ["OLD222"] and rows["PPRK22"]["merged"] == []
    assert rows["GQNE22"]["date"] == "About 1923-06" and rows["PPRK22"]["date"] is None
    assert rows["GQNE22"]["attention"] == "Deleted from Paperless" and rows["PPRK22"]["attention"] is None


def test_rows_sort_newest_first():
    assert [r["code"] for r in listing()] == ["MMGG22", "PPRK22", "GQNE22", "O0042"]


# ---- the API

CFG = SimpleNamespace(
    codes=True, gramps=GrampsConfig("http://g/api", "u", "p", public_url="https://g"),
    sync_paperless=SyncPaperlessConfig(sync_tags=("sync",), public_url="https://p", gramps_id_field_id=12,
                                       gramps_url_field_id=14),
    sync_immich=SyncImmichConfig(public_url="https://i", id_tag_prefix="ID"))


def make_app(gramps=None, paperless=None, immich=None):
    app = FastAPI()
    app.include_router(media_routes.router)
    app.state.gramps = gramps or FakeGramps()
    app.state.paperless = paperless
    app.state.immich_accounts = [immich] if immich else []
    app.state.caches = {"stale": 1}
    app.state.cfg = CFG
    return app


def call(app, method, url, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://b") as c:
            return await c.request(method, url, **kw)
    return asyncio.run(go())


def world():
    gr = FakeGramps(
        media={"PPRK22": media("PPRK22", attrs=[attr("Paperless ID", "7")], notes=["n1", "n2"]),
               "GQNE22": media("GQNE22", attrs=[attr("Paperless ID", "8")]),
               "MMGG22": media("MMGG22", mime="image/jpeg", attrs=[attr("Immich ID", "a1")])},
        notes={"n1": {"handle": "n1", "gramps_id": "N0001", "type": "Transcription"},
               "n2": {"handle": "n2", "gramps_id": "N0002", "type": "Research"}},
        holders={"p1": {"handle": "p1", "media_list": [{"ref": "h-PPRK22", "rect": [1, 2, 3, 4]}]},
                 "p2": {"handle": "p2", "media_list": [{"ref": "h-PPRK22", "rect": []},
                                                       {"ref": "h-GQNE22", "rect": []}]}})
    return gr, FakePaperless([document(7, "PPRK22")])


def test_api_list():
    gr, pl = world()
    body = call(make_app(gr, pl), "GET", "/media/api/list").json()
    assert {r["code"]: r["attention"] for r in body["items"]} == {
        "PPRK22": None, "GQNE22": "Deleted from Paperless", "MMGG22": None}


def test_api_list_answers_without_gramps_or_paperless():
    assert call(make_app(FakeGramps(down=True)), "GET", "/media/api/list").status_code == 503
    gr = FakeGramps(media={"GQNE22": media("GQNE22", attrs=[attr("Paperless ID", "8")])})
    for pl in (FakePaperless(down=True), None):
        assert call(make_app(gr, pl), "GET", "/media/api/list").json()["items"][0]["attention"] is None


def test_api_delete_removes_the_media_its_own_notes_and_the_documents_marks():
    gr, pl = world()
    app = make_app(gr, pl)
    r = call(app, "DELETE", "/media/api/pprk-22")
    assert r.status_code == 200 and r.json() == {"code": "PPRK22", "problems": []}
    assert "PPRK22" not in gr.media and gr.deleted_notes == ["n1"] and "n2" in gr.notes
    assert gr.holders["p1"]["media_list"] == [] and app.state.caches == {}
    doc = pl.docs[7]
    assert doc["tags"] == [9]
    assert [cf["value"] for cf in doc["custom_fields"]] == [None, None, "kept"]
    assert call(app, "DELETE", "/media/api/PPRK22").status_code == 404


def test_api_delete_releases_the_photo(monkeypatch):
    monkeypatch.setattr(sync_immich, "UNTAG_PAUSE", 0)
    gr, _pl = world()
    a = {**asset("a1"), "tags": [{"value": "Sync/Gramps"}, {"value": "ID/MMGG22"}, {"value": "Family"}]}
    im = FakeImmich(assets={"a1": a})
    im.metadata["a1"] = {"bifrost": {"gramps_id": "MMGG22"}}
    assert call(make_app(gr, None, im), "DELETE", "/media/api/MMGG22").json()["problems"] == []
    assert [t["value"] for t in a["tags"]] == ["Family"] and im.metadata["a1"] == {}


def test_api_delete_reports_a_source_it_could_not_release():
    gr, _pl = world()
    r = call(make_app(gr, FakePaperless(down=True)), "DELETE", "/media/api/PPRK22").json()
    assert "PPRK22" not in gr.media and "Paperless document 7" in r["problems"][0]


def test_api_merge_moves_the_references_and_deletes_the_first():
    gr, pl = world()
    r = call(make_app(gr, pl), "POST", "/media/api/PPRK22/merge", json={"into": "gqne22"})
    assert r.status_code == 200 and r.json() == {"code": "PPRK22", "problems": [], "into": "GQNE22", "moved": 2}
    assert "PPRK22" not in gr.media and "GQNE22" in gr.media
    assert gr.holders["p1"]["media_list"] == [{"ref": "h-GQNE22", "rect": [1, 2, 3, 4]}]
    assert gr.holders["p2"]["media_list"] == [{"ref": "h-GQNE22", "rect": []}]
    assert pl.docs[7]["tags"] == [9]
    assert codes.merged_ids(gr.media["GQNE22"]) == ["PPRK22"]
    assert "backlinks" not in gr.media["GQNE22"] and "extended" not in gr.media["GQNE22"]


def test_a_second_merge_adds_to_the_record_and_carries_the_first_ones_over():
    gr, pl = world()
    call(make_app(gr, pl), "POST", "/media/api/PPRK22/merge", json={"into": "GQNE22"})
    call(make_app(gr, pl), "POST", "/media/api/GQNE22/merge", json={"into": "MMGG22"})
    assert codes.merged_ids(gr.media["MMGG22"]) == ["PPRK22", "GQNE22"]
    assert [a["type"] for a in gr.media["MMGG22"]["attribute_list"]][0] == "Immich ID"


@pytest.mark.parametrize("code,into,status", [("PPRK22", "PPRK22", 400), ("PPRK22", "NOPE22", 404),
                                              ("NOPE22", "PPRK22", 404), ("PPRK22", "", 404)])
def test_api_merge_refusals(code, into, status):
    gr, pl = world()
    assert call(make_app(gr, pl), "POST", f"/media/api/{code}/merge", json={"into": into}).status_code == status
    assert "PPRK22" in gr.media and pl.docs[7]["tags"] == [DOC_TAG, 9]


def test_api_thumbnail():
    gr, pl = world()
    r = call(make_app(gr, pl), "GET", "/media/api/pprk22/thumbnail")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert call(make_app(gr, pl), "GET", "/media/api/NOPE22/thumbnail").status_code == 404


def test_a_duplicate_can_be_merged_away_without_unsyncing_the_document():
    gr, pl = world()
    gr.media["DUPL22"] = media("DUPL22", attrs=[attr("Paperless ID", "7")])
    r = call(make_app(gr, pl), "POST", "/media/api/DUPL22/merge", json={"into": "PPRK22"})
    assert r.status_code == 200 and "DUPL22" not in gr.media
    assert pl.docs[7]["tags"] == [DOC_TAG, 9] and pl.docs[7]["custom_fields"][0]["value"] == "PPRK22"
