"""Citations wizard: Gramps Sources and Citations, and the Paperless scan filed with them"""

import asyncio
import copy

import pytest

from bifrost.core import db
from bifrost.core.clients.paperless import PaperlessClient, PaperlessError
from bifrost.core.config import SyncPaperlessConfig
from bifrost.modules import citations
from bifrost.modules.citations import CitationError

CFG = SyncPaperlessConfig(gramps_id_field_id=1, source_url_field_id=4)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "bifrost.db")
    yield c
    c.close()
MEANING = {"id": 5, "name": "Date meaning", "data_type": "select",
           "extra_data": {"select_options": [{"id": "ev", "label": "Event"}, {"id": "cr", "label": "Creation"}]}}


class FakeGramps:
    def __init__(self):
        self.objects = {
            "sources": {"src1": {"handle": "src1", "gramps_id": "S0007", "title": "Old source", "reporef_list": [
                {"ref": "rep1", "call_number": "C/7"}]}},
            "repositories": {"rep1": {"handle": "rep1", "gramps_id": "R0002", "name": "Värmlandsarkiv", "type": "Archive"}},
            "citations": {
                "cit1": {"handle": "cit1", "gramps_id": "C0041", "page": "p. 9", "source_handle": "src1",
                         "confidence": 3, "change": 100, "note_list": ["n0", "n1"]},
                "cit2": {"handle": "cit2", "gramps_id": "C0043", "page": "p. 9, Anna", "source_handle": "src1",
                         "confidence": 2, "change": 200}},
            "notes": {"n0": {"handle": "n0", "gramps_id": "N0098", "text": {"string": "Transcription: …"}},
                      "n1": {"handle": "n1", "gramps_id": "N0099",
                             "text": {"string": "FIRST REFERENCE NOTE:\nOld FRN.\n\nSHORT REFERENCE NOTE:\nOld SRN.\n"}}},
            "media": {"med1": {"handle": "med1", "gramps_id": "NC3MPQ"}},
        }
        self.created = []

    async def _paged(self, path, **params):
        return [copy.deepcopy(o) for o in self.objects[path.strip("/")].values()]

    async def get_object(self, api_path, handle, **params):
        return copy.deepcopy(self.objects[api_path][handle])

    async def get_media_by_gramps_id(self, gramps_id):
        return next((copy.deepcopy(m) for m in self.objects["media"].values() if m["gramps_id"] == gramps_id), None)

    async def get_media_backlinks(self, handle):
        return {"citation": [h for h in self.objects["citations"] if handle == "med1"]}

    async def create_objects(self, objs):
        self.created.append(objs)
        return []


class FakePaperless:
    custom_field_value = staticmethod(PaperlessClient.custom_field_value)

    def __init__(self, fail=None):
        self.docs = {7: {"id": 7, "title": "Anders Lindqvist birth record 1868", "created": "1868-03-14",
                         "document_type": None, "correspondent": 3,
                         "custom_fields": [{"field": 1, "value": "nc3mpq"}, {"field": 3, "value": "q1"},
                                           {"field": 4, "value": "https://old.example/7"}]},
                     8: {"id": 8, "title": "Unsynced", "custom_fields": []}}
        self.patches = []
        self.fail = fail

    async def get_document(self, doc_id):
        if doc_id not in self.docs:
            raise PaperlessError("GET /api/documents/9/ → 404: not found", status=404)
        return copy.deepcopy(self.docs[doc_id])

    async def document_types(self):
        return [{"id": 25, "name": "Vital record"}]

    async def correspondents(self):
        return [{"id": 3, "name": "ArkivDigital"}]

    async def custom_fields(self):
        return [{"id": 1, "name": "Gramps ID", "data_type": "string"}, MEANING]

    async def patch_document(self, doc_id, fields):
        if self.fail:
            raise PaperlessError(self.fail, status=500)
        self.patches.append((doc_id, fields))


SOURCE = {"title": "Sweden, Kalmar, Vimmerby, Födelse- och dopböcker [birth and baptism books] C:8, 1861–1875",
          "author": "Vimmerby församling", "abbrev": "Vimmerby dopbok C:8 (1861–1875)",
          "pubinfo": "Digital images, ArkivDigital (https://www.arkivdigital.se).", "call_number": "SE/VALA/23453/C/8",
          "repository": {"handle": "rep1"}}
CITATION = {"page": "p. 45 (image 48), no. 23, Anders Johan birth and baptism entry", "confidence": "Very High",
            "frn": "Vimmerby församling, … Anders Johan.", "srn": "Vimmerby dopbok C:8 (1861–1875), p. 45."}
SCAN = {"title": "Anders Johan birth and baptism entry 1868", "document_type": 25, "correspondent": 3,
        "date_meaning": "ev", "source_url": "https://www.arkivdigital.se/aid/show/v1.b48.s45"}


def create(gramps, paperless, source=SOURCE, citation=CITATION, scan=SCAN, doc_id=7):
    return asyncio.run(citations.create(gramps, paperless, CFG, doc_id, copy.deepcopy(source),
                                        copy.deepcopy(citation), copy.deepcopy(scan)))


def test_note_holds_both_reference_notes_under_their_headings():
    assert citations.note_text(" FRN. ", "SRN.\n") == "FIRST REFERENCE NOTE:\nFRN.\n\nSHORT REFERENCE NOTE:\nSRN."
    assert citations.reference_notes(citations.note_text("A, b.\nMore.", "C.")) == ("A, b.\nMore.", "C.")
    assert citations.reference_notes("Transcription: …") == ("", "")


def test_new_source_note_and_citation_go_to_gramps_in_one_batch():
    gramps, paperless = FakeGramps(), FakePaperless()
    result = create(gramps, paperless)
    assert len(gramps.created) == 1
    source, note, cit = gramps.created[0]
    assert source["_class"] == "Source" and source["gramps_id"] == "S0008"
    assert {k: source[k] for k in ("title", "author", "abbrev", "pubinfo")} == {
        k: SOURCE[k] for k in ("title", "author", "abbrev", "pubinfo")}
    assert [(r["ref"], r["call_number"]) for r in source["reporef_list"]] == [("rep1", "SE/VALA/23453/C/8")]
    assert (note["_class"], note["gramps_id"], note["type"]) == ("Note", "N0100", "Citation")
    assert note["text"]["string"] == citations.note_text(CITATION["frn"], CITATION["srn"])
    assert cit["_class"] == "Citation" and cit["gramps_id"] == "C0044"
    assert (cit["source_handle"], cit["page"], cit["confidence"]) == (source["handle"], CITATION["page"], 4)
    assert cit["note_list"] == [note["handle"]]
    assert [m["ref"] for m in cit["media_list"]] == ["med1"]
    assert "date" not in cit
    assert [(c["kind"], c["gramps_id"]) for c in result["created"]] == [
        ("source", "S0008"), ("citation", "C0044"), ("note", "N0100")]
    assert result["source"]["gramps_id"] == "S0008" and result["citation"]["gramps_id"] == "C0044"
    assert result["media"] == "NC3MPQ" and result["scan"] == 7 and result["scan_error"] is None


def test_the_scan_is_filed_with_its_other_custom_fields_kept():
    paperless = FakePaperless()
    create(FakeGramps(), paperless)
    [(doc_id, patch)] = paperless.patches
    assert doc_id == 7
    assert (patch["title"], patch["document_type"], patch["correspondent"]) == (SCAN["title"], 25, 3)
    assert sorted((f["field"], f["value"]) for f in patch["custom_fields"]) == [
        (1, "nc3mpq"), (3, "q1"), (4, SCAN["source_url"]), (5, "ev")]


def test_a_blank_source_url_or_date_meaning_leaves_the_scan_s_values():
    paperless = FakePaperless()
    create(FakeGramps(), paperless, scan={**SCAN, "source_url": " ", "date_meaning": None, "title": ""})
    [(_, patch)] = paperless.patches
    assert "title" not in patch
    assert sorted((f["field"], f["value"]) for f in patch["custom_fields"]) == [
        (1, "nc3mpq"), (3, "q1"), (4, "https://old.example/7")]


def test_no_scan_means_paperless_is_left_alone():
    paperless = FakePaperless()
    result = create(FakeGramps(), paperless, scan=None)
    assert paperless.patches == [] and result["scan"] is None


def test_an_existing_source_gets_only_the_citation_and_note():
    gramps = FakeGramps()
    result = create(gramps, FakePaperless(), source={"handle": "src1", "repository": {"handle": "rep1"}})
    [objs] = gramps.created
    assert [o["_class"] for o in objs] == ["Note", "Citation"]
    assert objs[1]["source_handle"] == "src1"
    assert result["source"] == {"handle": "src1", "gramps_id": "S0007", "title": "Old source"}
    assert [c["kind"] for c in result["created"]] == ["citation", "note"]


def test_a_source_without_repository_or_call_number_has_no_reporef():
    gramps = FakeGramps()
    create(gramps, FakePaperless(), source={**SOURCE, "call_number": "", "repository": None})
    assert gramps.created[0][0]["reporef_list"] == []


@pytest.mark.parametrize("source, citation, doc_id, status, message", [
    (SOURCE, {**CITATION, "confidence": "Sure"}, 7, 400, "Choose a confidence level"),
    (SOURCE, {**CITATION, "page": " "}, 7, 400, "The citation needs a page, an FRN, and an SRN"),
    ({**SOURCE, "title": " "}, CITATION, 7, 400, "The new Source needs a title"),
    ({**SOURCE, "repository": None}, CITATION, 7, 400, "A call number needs a Repository"),
    (SOURCE, CITATION, 8, 403, "Paperless document #8 isn't synced to Gramps"),
])
def test_refusals_write_nothing(source, citation, doc_id, status, message):
    gramps, paperless = FakeGramps(), FakePaperless()
    with pytest.raises(CitationError) as err:
        create(gramps, paperless, source=source, citation=citation, doc_id=doc_id)
    assert (err.value.status, str(err.value)) == (status, message)
    assert gramps.created == [] and paperless.patches == []


def test_a_document_whose_media_is_gone_is_refused():
    gramps = FakeGramps()
    gramps.objects["media"] = {}
    with pytest.raises(CitationError) as err:
        create(gramps, FakePaperless())
    assert (err.value.status, str(err.value)) == (409, "Gramps has no media NC3MPQ")
    assert gramps.created == []


def test_a_paperless_failure_after_gramps_is_reported_not_raised():
    gramps = FakeGramps()
    result = create(gramps, FakePaperless(fail="PATCH → 500: down"))
    assert len(gramps.created) == 1
    assert result["scan"] is None and result["scan_error"] == "PATCH → 500: down"


def test_document_lists_its_media_citations_newest_first_with_their_drafts(conn):
    citations.keep_draft(conn, "cit1", "se-dopbok", {"values": {"parish": "Vimmerby"}, "confidence": "High"})
    doc = asyncio.run(citations.document(FakeGramps(), FakePaperless(), CFG, 7, conn))
    assert (doc["pid"], doc["created"], doc["source_url"]) == ("NC3MPQ", "1868-03-14", "https://old.example/7")
    assert (doc["document_type"], doc["correspondent"], doc["date_meaning"]) == (None, 3, None)
    assert doc["media"] == {"handle": "med1", "gramps_id": "NC3MPQ"}
    assert doc["citations"] == [
        {"handle": "cit2", "gramps_id": "C0043", "page": "p. 9, Anna", "confidence": 2, "change": 200,
         "source_handle": "src1", "source": "Old source", "frn": "", "srn": "", "draft": None},
        {"handle": "cit1", "gramps_id": "C0041", "page": "p. 9", "confidence": 3, "change": 100,
         "source_handle": "src1", "source": "Old source", "frn": "Old FRN.", "srn": "Old SRN.",
         "draft": {"type": "se-dopbok", "draft": {"values": {"parish": "Vimmerby"}, "confidence": "High"}}}]
    with pytest.raises(CitationError) as err:
        asyncio.run(citations.document(FakeGramps(), FakePaperless(), CFG, 8, conn))
    assert err.value.status == 403


def test_kept_drafts_answer_only_for_the_citations_asked_about(conn):
    citations.keep_draft(conn, "cit1", "se-dopbok", {"values": {"parish": "Vimmerby"}})
    citations.keep_draft(conn, "cit1", "se-husforhor", {"values": {"parish": "Norra Ny"}})
    citations.keep_draft(conn, "cit9", "us-federal-census", {"values": {"year": "1920"}})
    assert citations.kept_drafts(conn, ["cit1", "cit2"]) == {
        "cit1": {"type": "se-husforhor", "draft": {"values": {"parish": "Norra Ny"}}}}
    assert citations.kept_drafts(conn, []) == {}


def test_context_names_each_source_s_repositories_and_finds_the_date_meaning_field(conn):
    ctx = asyncio.run(citations.context(FakeGramps(), FakePaperless(), conn))
    assert ctx["sources"] == [{"handle": "src1", "gramps_id": "S0007", "title": "Old source", "author": "",
                               "abbrev": "", "pubinfo": "",
                               "repositories": [{"name": "Värmlandsarkiv", "call_number": "C/7"}],
                               "remembered": None}]
    assert ctx["repositories"] == [{"handle": "rep1", "gramps_id": "R0002", "name": "Värmlandsarkiv", "type": "Archive"}]
    assert ctx["document_types"] == [{"id": 25, "name": "Vital record"}]
    assert ctx["date_meaning"] == {"field": 5, "options": MEANING["extra_data"]["select_options"]}


def test_remembered_inputs_follow_the_source_and_the_last_use(conn):
    citations.remember(conn, "src1", "se-dopbok", {"parish": "Vimmerby", "vol": "C:8"})
    citations.remember(conn, "src1", "se-husforhor", {"parish": "Norra Ny"})
    memory = citations.remembered(conn)
    assert list(memory) == ["src1"]
    assert (memory["src1"]["type"], memory["src1"]["inputs"]) == ("se-husforhor", {"parish": "Norra Ny"})
    ctx = asyncio.run(citations.context(FakeGramps(), FakePaperless(), conn))
    assert ctx["sources"][0]["remembered"]["inputs"] == {"parish": "Norra Ny"}


def citations_app(gramps, paperless, conn):
    from types import SimpleNamespace

    from fastapi import FastAPI

    from bifrost.web.routes import citations as routes
    app = FastAPI()
    app.include_router(routes.router)
    app.state.gramps = gramps
    app.state.paperless = paperless
    app.state.conn = conn
    app.state.cfg = SimpleNamespace(sync_paperless=CFG)
    return app


def call(app, method, url, **kw):
    import httpx

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://bifrost") as client:
            return await client.request(method, url, **kw)
    return asyncio.run(go())


def test_create_route_answers_with_what_was_made_or_why_not(conn):
    app = citations_app(FakeGramps(), FakePaperless(), conn)
    inputs = {"type": "se-dopbok", "values": {"parish": "Vimmerby", "vol": "C:8"}}
    draft = {"type": "se-dopbok", "draft": {"values": {"parish": "Vimmerby", "page": "45"}, "subject": {"name": "Anders Johan"},
                                            "confidence": "Very High", "variant": ""}}
    body = {"doc_id": 7, "source": SOURCE, "citation": CITATION, "scan": SCAN, "inputs": inputs, "draft": draft}
    r = call(app, "POST", "/citations/api/create", json=body)
    assert r.status_code == 200 and r.json()["citation"]["gramps_id"] == "C0044"
    assert citations.remembered(conn)[r.json()["source"]["handle"]]["inputs"] == inputs["values"]
    assert citations.kept_drafts(conn, [r.json()["citation"]["handle"]]) == {r.json()["citation"]["handle"]: draft}
    r = call(app, "POST", "/citations/api/create", json={**body, "doc_id": 8})
    assert r.status_code == 403 and r.json()["detail"] == "Paperless document #8 isn't synced to Gramps"
    r = call(app, "POST", "/citations/api/create",
             json={**body, "source": {**SOURCE, "repository": {"name": "New archive", "type": "Archive"}}})
    assert r.status_code == 422
    assert len(citations.remembered(conn)) == 1
    r = call(app, "GET", "/citations/api/doc/9")
    assert r.status_code == 404


def test_the_page_is_served(conn):
    r = call(citations_app(FakeGramps(), FakePaperless(), conn), "GET", "/citations")
    assert r.status_code == 200
    assert "<citations-wizard>" in r.text and "/static/app/citations-wizard.js" in r.text


class TaggingGramps(FakeGramps):
    def __init__(self, tags=None):
        super().__init__()
        self.objects["tags"] = dict(tags or {})

    async def get_tag_handle(self, name):
        return next((h for h, t in self.objects["tags"].items() if t["name"] == name), None)

    async def update_object(self, api_path, handle, obj):
        self.objects[api_path][handle] = copy.deepcopy(obj)
        return obj

    async def create_objects(self, objs):
        for o in objs:
            if o["_class"] == "Tag":
                self.objects["tags"][o["handle"]] = {"handle": o["handle"], "name": o["name"]}
        return await super().create_objects(objs)


def test_a_new_citation_carries_its_attributes_and_the_general_form_tag():
    gramps = TaggingGramps()
    pairs = [["Subject", "Anders Johan"], ["Record", "birth and baptism entry"], ["Bogus", "x"], ["Evidence", " "],
             ["Guide", "2026-10-13"]]
    create(gramps, FakePaperless(), citation={**CITATION, "attributes": pairs, "tag": "General form"})
    objs = gramps.created[0]
    tag = next(o for o in objs if o["_class"] == "Tag")
    cit = next(o for o in objs if o["_class"] == "Citation")
    assert tag["name"] == "General form" and cit["tag_list"] == [tag["handle"]]
    assert [(a["_class"], a["type"], a["value"]) for a in cit["attribute_list"]] == [
        ("SrcAttribute", "Subject", "Anders Johan"), ("SrcAttribute", "Record", "birth and baptism entry"),
        ("SrcAttribute", "Guide", "2026-10-13")]


def test_an_existing_tag_is_reused_and_no_tag_means_none():
    gramps = TaggingGramps(tags={"tg1": {"handle": "tg1", "name": "General form"}})
    create(gramps, FakePaperless(), citation={**CITATION, "tag": "General form"})
    objs = gramps.created[0]
    assert not [o for o in objs if o["_class"] == "Tag"]
    assert next(o for o in objs if o["_class"] == "Citation")["tag_list"] == ["tg1"]
    plain = TaggingGramps()
    create(plain, FakePaperless())
    assert next(o for o in plain.created[0] if o["_class"] == "Citation")["tag_list"] == []


def test_wizard_citations_lists_kept_drafts_as_gramps_holds_them(conn):
    citations.keep_draft(conn, "cit1", "se-dopbok", {"values": {"page": "9"}})
    citations.keep_draft(conn, "gone", "se-dopbok", {"values": {}})
    gramps = TaggingGramps(tags={"tg1": {"handle": "tg1", "name": "General form"}})
    gramps.objects["citations"]["cit1"]["tag_list"] = ["tg1"]
    gramps.objects["citations"]["cit1"]["attribute_list"] = [{"type": "_APID", "value": "1,2::3"}]
    [row] = asyncio.run(citations.wizard_citations(gramps, conn))
    assert (row["handle"], row["gramps_id"], row["page"]) == ("cit1", "C0041", "p. 9")
    assert (row["frn"], row["srn"], row["note"]) == ("Old FRN.", "Old SRN.", "n1")
    assert row["attributes"] == [["_APID", "1,2::3"]] and row["tags"] == ["General form"]
    assert row["source"]["title"] == "Old source" and row["draft"] == {"type": "se-dopbok", "draft": {"values": {"page": "9"}}}


def test_rebuild_rewrites_page_attributes_tag_and_notes_and_keeps_other_attributes(conn):
    gramps = TaggingGramps()
    gramps.objects["citations"]["cit1"]["attribute_list"] = [
        {"_class": "SrcAttribute", "type": "_APID", "value": "1,2::3", "private": False}, {"type": "Subject", "value": "old"}]
    items = [{"handle": "cit1", "page": "p. 9 (birth and baptism)", "attributes": [["Subject", "Anders Johan"], ["Guide", "2026-10-13"]],
              "tagged": True, "note": "n1", "frn": "New FRN.", "srn": "New SRN.",
              "draft": {"type": "se-dopbok", "draft": {"guide": "2026-10-13"}}}]
    assert asyncio.run(citations.rebuild(gramps, conn, items, "General form")) == {"rebuilt": ["C0041"], "failed": []}
    cit = gramps.objects["citations"]["cit1"]
    assert cit["page"] == "p. 9 (birth and baptism)"
    assert [(a["type"], a["value"]) for a in cit["attribute_list"]] == [("_APID", "1,2::3"), ("Subject", "Anders Johan"),
                                                                       ("Guide", "2026-10-13")]
    assert cit["tag_list"] == list(gramps.objects["tags"])
    assert gramps.objects["notes"]["n1"]["text"]["string"] == citations.note_text("New FRN.", "New SRN.")
    assert citations.kept_drafts(conn, ["cit1"])["cit1"]["draft"] == {"guide": "2026-10-13"}
    untag = [{"handle": "cit1", "tagged": False}]
    asyncio.run(citations.rebuild(gramps, conn, untag, "General form"))
    assert gramps.objects["citations"]["cit1"]["tag_list"] == []


def test_rebuild_reports_a_citation_it_could_not_write(conn):
    got = asyncio.run(citations.rebuild(TaggingGramps(), conn, [{"handle": "nope", "page": "x"}], "General form"))
    assert got["rebuilt"] == [] and got["failed"][0]["handle"] == "nope"


def test_the_rebuild_page_and_list_are_served(conn):
    citations.keep_draft(conn, "cit1", "se-dopbok", {"values": {}})
    app = citations_app(TaggingGramps(), FakePaperless(), conn)
    r = call(app, "GET", "/citations/rebuild")
    assert r.status_code == 200 and "<citations-rebuild>" in r.text and "/static/app/citations-rebuild.js" in r.text
    r = call(app, "GET", "/citations/api/rebuild")
    assert r.status_code == 200 and [i["gramps_id"] for i in r.json()["items"]] == ["C0041"]
