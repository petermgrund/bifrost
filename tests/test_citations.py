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
            "citations": {"cit1": {"handle": "cit1", "gramps_id": "C0041", "page": "p. 9", "source_handle": "src1"}},
            "notes": {"n1": {"handle": "n1", "gramps_id": "N0099"}},
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
    assert cit["_class"] == "Citation" and cit["gramps_id"] == "C0042"
    assert (cit["source_handle"], cit["page"], cit["confidence"]) == (source["handle"], CITATION["page"], 4)
    assert cit["note_list"] == [note["handle"]]
    assert [m["ref"] for m in cit["media_list"]] == ["med1"]
    assert "date" not in cit
    assert [(c["kind"], c["gramps_id"]) for c in result["created"]] == [
        ("source", "S0008"), ("citation", "C0042"), ("note", "N0100")]
    assert result["source"]["gramps_id"] == "S0008" and result["citation"]["gramps_id"] == "C0042"
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


def test_document_lists_its_media_citations_and_scan_values():
    doc = asyncio.run(citations.document(FakeGramps(), FakePaperless(), CFG, 7))
    assert (doc["pid"], doc["created"], doc["source_url"]) == ("NC3MPQ", "1868-03-14", "https://old.example/7")
    assert (doc["document_type"], doc["correspondent"], doc["date_meaning"]) == (None, 3, None)
    assert doc["media"] == {"handle": "med1", "gramps_id": "NC3MPQ"}
    assert doc["citations"] == [{"gramps_id": "C0041", "page": "p. 9", "source": "Old source"}]
    with pytest.raises(CitationError) as err:
        asyncio.run(citations.document(FakeGramps(), FakePaperless(), CFG, 8))
    assert err.value.status == 403


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
    body = {"doc_id": 7, "source": SOURCE, "citation": CITATION, "scan": SCAN, "inputs": inputs}
    r = call(app, "POST", "/citations/api/create", json=body)
    assert r.status_code == 200 and r.json()["citation"]["gramps_id"] == "C0042"
    assert citations.remembered(conn)[r.json()["source"]["handle"]]["inputs"] == inputs["values"]
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
