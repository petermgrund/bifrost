"""Codes: the Gramps media with a code as id, plus the withdrawn-codes note"""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core import ids
from bifrost.core.clients.gramps import GrampsError
from bifrost.core.config import SyncImmichConfig, SyncPaperlessConfig
from bifrost.modules import codes
from bifrost.web.routes import codes as codes_routes

NOTE_TEXT = "77N7CS 2026-09-30 duplicate\nnot a code line\nKSP8JF 2026-10-01\nC8T5 2026-09-30 retired"


def attr(name, value):
    return {"type": name, "value": value}


def media(gid, desc="A letter", change=1_792_000_000, mime="application/pdf", attrs=()):
    return {"gramps_id": gid, "handle": f"h-{gid}", "desc": desc, "change": change, "mime": mime,
            "attribute_list": list(attrs)}


def withdrawn_note(text=NOTE_TEXT, handle="wn", gid="N0005"):
    return {"handle": handle, "gramps_id": gid, "type": codes.NOTE_TYPE,
            "text": {"_class": "StyledText", "string": text, "tags": []}}


class FakeGramps:
    def __init__(self, media=None, notes=None, down=False):
        self.media = media or {}
        self.notes = notes or {}
        self.down = down
        self.created_notes = []
        self.updated_notes = []

    def _check(self):
        if self.down:
            raise GrampsError("GET /media/ → 502")

    async def list_media(self, keys=None):
        self._check()
        return list(self.media.values())

    async def list_media_gramps_ids(self):
        self._check()
        return set(self.media)

    async def get_media_by_gramps_id(self, gid, backlinks=False, notes=False):
        self._check()
        return self.media.get(gid)

    async def find_notes(self, note_type):
        self._check()
        return [n for n in self.notes.values() if n["type"] == note_type]

    async def next_note_id(self):
        return ids.next_sequential_id("N", {n["gramps_id"] for n in self.notes.values()})

    async def create_note(self, obj):
        self.notes[obj["handle"]] = obj
        self.created_notes.append(obj)

    async def update_note(self, handle, obj):
        self.notes[handle] = obj
        self.updated_notes.append(obj)

    async def media_thumbnail(self, handle, size=64):
        return b"png", "image/png"


class FakePaperless:
    def __init__(self, doc_ids=(7,), values=None, down=False):
        self.doc_ids, self.values, self.down = set(doc_ids), values or {}, down

    async def document_ids(self):
        if self.down:
            raise RuntimeError("paperless down")
        return set(self.doc_ids)

    async def custom_field_values(self, field_id, ids=None):
        if self.down:
            raise RuntimeError("paperless down")
        return dict(self.values)


def run(coro):
    return asyncio.run(coro)


# ---- the note

def test_parse_note_reads_code_date_and_reason_and_skips_other_lines():
    assert codes.parse_note(NOTE_TEXT) == {
        "77N7CS": {"withdrawn": "2026-09-30", "reason": "duplicate"},
        "KSP8JF": {"withdrawn": "2026-10-01", "reason": ""},
        "C8T5": {"withdrawn": "2026-09-30", "reason": "retired"},
    }
    assert codes.parse_note("") == {} and codes.parse_note(None) == {}


def test_note_line():
    assert codes.note_line("ABC234", "2026-11-02", "a test") == "ABC234 2026-11-02 a test"
    assert codes.note_line("ABC234", "2026-11-02", "") == "ABC234 2026-11-02"


def test_withdrawn_reads_the_note_or_nothing():
    assert run(codes.withdrawn(FakeGramps())) == {}
    gr = FakeGramps(notes={"wn": withdrawn_note()})
    assert set(run(codes.withdrawn(gr))) == {"77N7CS", "KSP8JF", "C8T5"}


def test_withdraw_creates_the_note_then_appends_to_it():
    gr = FakeGramps(notes={"other": {"handle": "other", "gramps_id": "N0001", "type": "Research",
                                     "text": {"string": "x"}}})
    assert run(codes.withdraw(gr, " abc-234 ", "  a   test ", when="2026-11-02")) == "ABC234"
    (note,) = gr.created_notes
    assert note["type"] == codes.NOTE_TYPE and note["gramps_id"] == "N0002"
    assert note["text"]["string"] == "ABC234 2026-11-02 a test"
    run(codes.withdraw(gr, "DEF567", "merged into ABC234", when="2026-11-03"))
    assert gr.created_notes == [note]
    assert gr.updated_notes[-1]["text"]["string"] == "ABC234 2026-11-02 a test\nDEF567 2026-11-03 merged into ABC234"
    assert set(run(codes.withdrawn(gr))) == {"ABC234", "DEF567"}


@pytest.mark.parametrize("code,reason,status", [
    ("", "x", 400), ("ABC234", "   ", 400), ("ABC234", "r" * (codes.REASON_MAX + 1), 400),
    ("77N7CS", "again", 409),
])
def test_withdraw_refusals(code, reason, status):
    gr = FakeGramps(notes={"wn": withdrawn_note()})
    with pytest.raises(codes.CodeError) as exc:
        run(codes.withdraw(gr, code, reason))
    assert exc.value.status == status and gr.updated_notes == [] and gr.created_notes == []


# ---- hand-written codes

WITHDRAWN = codes.parse_note(NOTE_TEXT)


def test_check_code_normalizes_a_hand_written_code():
    assert codes.check_code(" phkn-3d ", set(), {}) == "PHKN3D"


@pytest.mark.parametrize("raw,status,msg", [
    ("", 400, "Type the code"),
    ("ABCDEI", 400, "contains I"),
    ("ABC23", 400, "has 5 characters"),
    ("234567", 400, "all digits"),
    ("README", 400, "reserved word"),
    ("77N7CS", 409, "withdrawn on 2026-09-30: duplicate"),
    ("QVWX22", 409, "already the ID of a Gramps media"),
    ("PPRK22", 409, "Paperless document 12, 13"),
])
def test_check_code_refusals(raw, status, msg):
    with pytest.raises(codes.CodeError) as exc:
        codes.check_code(raw, {"QVWX22"}, WITHDRAWN, {"PPRK22": [12, 13]})
    assert exc.value.status == status and msg in exc.value.detail


# ---- the list

URLS = codes.Urls(gramps="https://g", paperless="https://p", immich="https://i")


def listing(**kw):
    all_media = [
        media("PPRK22", attrs=[attr("Paperless URL", "u"), attr("Paperless ID", "7")], change=1_792_000_100),
        media("GQNE22", attrs=[attr("Paperless ID", "8")], change=1_792_000_050),
        media("MMGG22", desc="Farm", mime="image/jpeg", attrs=[attr("Immich ID", "a1")], change=1_792_000_200),
        media("77N7CS", attrs=[attr("Paperless ID", "9")], change=1_792_000_000),
        media("N0001", desc="not a code", attrs=[]),
        media("PXAWN2", desc="hand-made", mime="image/png", attrs=[]),
    ]
    return codes.rows(all_media, WITHDRAWN, URLS, **kw)


def by_code(**kw):
    return {r["code"]: r for r in listing(**kw)}


def test_rows_cover_media_with_a_code_and_the_withdrawn_entries():
    rows = by_code(documents={"7", "9"})
    assert set(rows) == {"PPRK22", "GQNE22", "MMGG22", "77N7CS", "PXAWN2", "KSP8JF", "C8T5"}
    assert rows["PPRK22"]["status"] == "in use" and rows["PPRK22"]["attention"] is None
    assert (rows["PPRK22"]["type"], rows["PPRK22"]["title"], rows["PPRK22"]["gramps"]) == ("document", "A letter", True)
    assert rows["PPRK22"]["paperless"] == [{"id": "7", "url": "https://p/documents/7/details"}]
    assert rows["PPRK22"]["gramps_url"] == "https://g/media/PPRK22"
    assert rows["MMGG22"]["immich"] == [{"id": "a1", "url": "https://i/photos/a1"}] and rows["MMGG22"]["type"] == "image"
    assert rows["PXAWN2"]["type"] == "image" and rows["PXAWN2"]["paperless"] == []
    assert (rows["KSP8JF"]["status"], rows["KSP8JF"]["gramps"], rows["KSP8JF"]["withdrawn"]) == ("withdrawn", False, "2026-10-01")
    assert rows["KSP8JF"]["updated"] == "2026-10-01" and rows["KSP8JF"]["title"] is None


def test_the_attention_cases():
    rows = by_code(documents={"7", "9"})
    assert rows["GQNE22"]["attention"] == "Deleted from Paperless"
    assert rows["77N7CS"]["attention"] == "Withdrawn but still in Gramps"
    assert rows["77N7CS"]["status"] == "withdrawn" and rows["77N7CS"]["withdrawn_reason"] == "duplicate"
    assert by_code()["GQNE22"]["attention"] is None


def test_rows_sort_newest_first():
    assert [r["code"] for r in listing()] == ["MMGG22", "PPRK22", "GQNE22", "77N7CS", "PXAWN2", "KSP8JF", "C8T5"]


def test_only_and_search_and_counts():
    assert [r["code"] for r in listing(only=["pprk-22", "KSP8JF"])] == ["PPRK22", "KSP8JF"]
    rows = listing(documents={"7", "9"})
    assert [r["code"] for r in codes.search(rows, "farm")] == ["MMGG22"]
    assert [r["code"] for r in codes.search(rows, "dupli")] == ["77N7CS"]
    assert {r["code"] for r in codes.search(rows, " 22")} == {"PPRK22", "GQNE22", "MMGG22"}
    assert codes.counts(rows) == {"all": 7, "in use": 4, "withdrawn": 3, "attention": 2}
    assert [r["code"] for r in rows if codes.matches(r, "attention")] == ["GQNE22", "77N7CS"]
    assert all(codes.matches(r, None) for r in rows)


@pytest.mark.parametrize("raw,wanted", [
    ("", None), ("all", None), ("in_use", "in use"), ("In-Use", "in use"), ("withdrawn", "withdrawn"),
    ("needs attention", "attention"), ("attention", "attention"),
])
def test_status_filter(raw, wanted):
    assert codes.status_filter(raw) == wanted


def test_status_filter_rejects_garbage():
    with pytest.raises(ValueError):
        codes.status_filter("reserved")


# ---- the API

def make_app(gramps=None, paperless=None):
    app = FastAPI()
    app.include_router(codes_routes.router)
    app.state.gramps = gramps or FakeGramps()
    app.state.paperless = paperless or FakePaperless()
    app.state.cfg = SimpleNamespace(
        sync_paperless=SyncPaperlessConfig(public_url="https://p", gramps_public_url="https://g",
                                           gramps_id_field_id=12),
        sync_immich=SyncImmichConfig(public_url="https://i"))
    return app


def call(app, method, url, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://b") as c:
            return await c.request(method, url, **kw)
    return asyncio.run(go())


def world():
    gr = FakeGramps(media={"PPRK22": media("PPRK22", attrs=[attr("Paperless ID", "7")]),
                           "GQNE22": media("GQNE22", attrs=[attr("Paperless ID", "8")])},
                    notes={"wn": withdrawn_note()})
    return gr, FakePaperless(doc_ids=(7,), values={7: "PPRK22", 40: "TYPED2"})


def test_api_list_filters():
    gr, pl = world()
    body = call(make_app(gr, pl), "GET", "/codes/api/list").json()
    assert body["gramps"] == "ok" and body["counts"] == {"all": 5, "in use": 2, "withdrawn": 3, "attention": 1}
    assert [r["code"] for r in body["items"]][:2] == ["GQNE22", "PPRK22"]
    body = call(make_app(gr, pl), "GET", "/codes/api/list", params={"status": "attention"}).json()
    assert [r["code"] for r in body["items"]] == ["GQNE22"]
    body = call(make_app(gr, pl), "GET", "/codes/api/list", params={"q": "dupl"}).json()
    assert [r["code"] for r in body["items"]] == ["77N7CS"]
    assert call(make_app(gr, pl), "GET", "/codes/api/list", params={"status": "reserved"}).status_code == 400


def test_api_list_answers_without_gramps_or_paperless():
    body = call(make_app(FakeGramps(down=True), FakePaperless(down=True)), "GET", "/codes/api/list")
    assert body.status_code == 503
    gr = FakeGramps(media={"PPRK22": media("PPRK22", attrs=[attr("Paperless ID", "7")])})
    body = call(make_app(gr, FakePaperless(down=True)), "GET", "/codes/api/list").json()
    assert body["gramps"] == "ok" and body["items"][0]["attention"] is None


def test_api_withdraw():
    gr, pl = world()
    app = make_app(gr, pl)
    r = call(app, "POST", "/codes/api/pprk22/withdraw", json={"reason": "a duplicate"})
    assert r.status_code == 200
    item = r.json()["item"]
    assert (item["code"], item["status"], item["withdrawn_reason"]) == ("PPRK22", "withdrawn", "a duplicate")
    assert item["attention"] == "Withdrawn but still in Gramps" and item["gramps"] is True
    assert gr.updated_notes[-1]["text"]["string"].endswith("PPRK22 " + item["withdrawn"] + " a duplicate")
    r = call(app, "POST", "/codes/api/PPRK22/withdraw", json={"reason": "again"})
    assert r.status_code == 409
    assert call(app, "POST", "/codes/api/NEW222/withdraw", json={"reason": ""}).status_code == 400


def test_api_thumbnail():
    gr, pl = world()
    r = call(make_app(gr, pl), "GET", "/codes/api/pprk22/thumbnail")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert call(make_app(gr, pl), "GET", "/codes/api/NOPE22/thumbnail").status_code == 404


def test_page_route_redirects_to_the_section():
    r = call(make_app(), "GET", "/codes")
    assert r.status_code == 307 and r.headers["location"] == "/#codes"
