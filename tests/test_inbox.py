"""Inbox: records captured during research, filed in Paperless and Gramps, listed until a citation shows them"""

import asyncio
import io
from types import SimpleNamespace

import pypdfium2 as pdfium
import pytest
from PIL import Image

from bifrost.core import db
from bifrost.core.clients.paperless import PaperlessClient
from bifrost.core.config import SyncPaperlessConfig
from bifrost.core.events import SyncEvent
from bifrost.modules import inbox
from bifrost.modules.inbox import CaptureError
from bifrost.web.routes import inbox as routes

CFG = SyncPaperlessConfig(sync_tags=("doc", "img"), gramps_id_field_id=1, gramps_url_field_id=2,
                          source_url_field_id=4, ocr_tag="Gemini OCR")
LINK = "https://www.familysearch.org/ark:/61903/3:1:3QS7-L99T-2SDQ"
CRUMB = "Minnesota, Marshall County, land miscellaneous records › Miscellaneous record, Vol. K, 1919-1927"
DETAILS = {"collection": CRUMB, "reference": "DGS 005537573", "image": "32", "images": "644"}


def jpeg(color="red", size=(60, 80)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "bifrost.db")
    yield c
    c.close()


class FakePaperless:
    custom_field_value = staticmethod(PaperlessClient.custom_field_value)

    def __init__(self, task=None, docs=None, same=()):
        self.tags = {"doc": 10, "img": 11, "Gemini OCR": 30}
        self.uploads = []
        self.notes = []
        self.task = task
        self.docs = docs or []
        self.same = list(same)

    async def documents_with_bytes(self, data):
        return self.same

    async def resolve_tag_id(self, name):
        return self.tags.get(name)

    async def correspondents(self):
        return [{"id": 1, "name": "Ancestry.com"}, {"id": 2, "name": "FamilySearch"}]

    async def post_document(self, data, filename, mime, **meta):
        self.uploads.append({"data": data, "filename": filename, "mime": mime, **meta})
        return "task-1"

    async def task_status(self, task_id):
        return self.task

    async def add_note(self, doc_id, text):
        self.notes.append((doc_id, text))

    async def get_document(self, doc_id):
        return {"id": doc_id, "custom_fields": []}

    async def documents_with_field(self, field_id, fields):
        return self.docs


class FakeGramps:
    def __init__(self, cited=()):
        self.cited = set(cited)

    async def cited_media_ids(self):
        return self.cited


def state_of(paperless, conn, gramps=None):
    return SimpleNamespace(paperless=paperless, gramps=gramps or FakeGramps(), conn=conn, caches={},
                           gemini=None, cfg=SimpleNamespace(sync_paperless=CFG, gemini=None))


def saved(conn, transcribe=False, note="Power of attorney section for PL Grund."):
    return inbox.insert_capture(conn, title="POA", link=LINK, details=DETAILS, note=note,
                                transcribe=transcribe, file_name="image.jpg", pages=1, task_id="task-1")


def test_read_paste_takes_familysearch_details_apart():
    text = (f"{LINK}\nMinnesota, Marshall County, land miscellaneous records > Miscellaneous record, Vol. K,"
            " 1919-1927\nImage 32 of 644\nImage Group Number (DGS): 005537573")
    assert inbox.read_paste(text) == {"link": LINK, "platform": "FamilySearch", **DETAILS}


def test_read_paste_reads_film_links_and_labels_on_their_own_line():
    found = inbox.read_paste("https://www.familysearch.org/search/film/005537573?i=31&cat=1031440")
    assert (found["reference"], found["image"], found["platform"]) == ("DGS 005537573", "32", "FamilySearch")
    assert inbox.read_paste("Image Group Number (DGS)\n005537573\nMiscellaneous record, Vol. K, 1919-1927") == {
        "reference": "DGS 005537573", "collection": "Miscellaneous record, Vol. K, 1919-1927"}
    assert inbox.read_paste("Miscellaneous record, Vol. K, p. 296")["page"] == "296"


def test_read_paste_names_other_platforms_by_host():
    found = inbox.read_paste("see https://www.ancestry.com/discoveryui-content/view/123:6061?tid=1.")
    assert found == {"link": "https://www.ancestry.com/discoveryui-content/view/123:6061?tid=1", "platform": "Ancestry"}
    assert inbox.platform_of("https://www.example.org/x") == "example.org"
    assert inbox.read_paste("   ") == {}


def test_read_paste_reads_ancestry_source_citations():
    text = ("Year: 1920; Census Place: Duluth Ward 6, St Louis, Minnesota; Roll: T625_859; Page: 8A; "
            "Enumeration District: 139\nSource Information\nAncestry.com. 1920 United States Federal Census "
            "[database on-line]. Lehi, UT, USA: Ancestry.com Operations, Inc., 2010.")
    assert inbox.read_paste(text) == {"reference": "Roll T625_859", "page": "8A",
                                      "collection": "1920 United States Federal Census"}
    found = inbox.read_paste("Ancestry.com. U.S., World War II Draft Registration Cards, 1942 [database on-line].")
    assert found["collection"] == "U.S., World War II Draft Registration Cards, 1942"


def test_read_paste_reads_arkivdigital_source_lines_and_links():
    line = "Ambjörby (S) AI:11 (1826-1830) Bild 45 / sid 87 (AID: v123456.b45.s87, NAD: SE/VA/13227)"
    assert inbox.read_paste(line) == {"reference": "AID v123456.b45.s87 · NAD SE/VA/13227", "image": "45",
                                      "page": "87", "collection": "Ambjörby (S) AI:11 (1826-1830)"}
    found = inbox.read_paste("https://www.arkivdigital.se/aid/show/v123456.b45.s87")
    assert (found["platform"], found["reference"], found["image"], found["page"]) == (
        "ArkivDigital", "AID v123456.b45.s87", "45", "87")


def test_match_name_ignores_case_punctuation_and_dot_com():
    options = [{"id": 1, "name": "Ancestry.com"}, {"id": 2, "name": "FamilySearch"}, {"id": 3, "name": "Find A Grave"}]
    assert inbox.match_name("Ancestry", options) == 1
    assert inbox.match_name("Find a Grave", options) == 3
    assert inbox.match_name("familysearch", options) == 2
    assert inbox.match_name("ArkivDigital", options) is None
    assert inbox.match_name("", options) is None


def test_fallback_title_uses_the_collection_and_image_else_the_file_name():
    assert inbox.fallback_title(DETAILS, "image.jpg") == "Miscellaneous record, Vol. K, 1919-1927, image 32"
    assert inbox.fallback_title({**DETAILS, "page": "296"}, "x.jpg") == "Miscellaneous record, Vol. K, 1919-1927, page 296"
    assert inbox.fallback_title({"image": "7"}, "x.jpg") == "Image 7"
    assert inbox.fallback_title({}, "image (3).jpg") == "Image (3)"


def test_paperless_note_puts_the_typed_note_first_then_where_it_is():
    assert inbox.paperless_note("Possibly 1919, look closer.", LINK, DETAILS) == (
        f"Possibly 1919, look closer.\n\n{CRUMB}\nDGS 005537573, image 32 of 644\n{LINK}")
    assert inbox.where({"page": "87", "image": "45"}) == "Page 87, image 45"
    assert inbox.paperless_note("Just this.", "", {}) == "Just this."
    assert inbox.paperless_note("", "", {"image": "4"}) == "Image 4"
    assert inbox.paperless_note("", "", {}) == ""


def test_consume_error_names_the_duplicate():
    assert inbox.consume_error("Not consuming image.jpg: It is a duplicate of Old deed (#123).") == (
        "Already in Paperless as #123")
    assert inbox.consume_error("Unsupported mime type") == "Unsupported mime type"
    assert inbox.consume_error(None) == "Paperless refused the file"


def test_file_store_holds_known_files_and_refuses_others():
    store = inbox.FileStore()
    held = store.add("image.jpg", jpeg())
    assert (held["mime"], held["pages"], held["name"]) == ("image/jpeg", 1, "image.jpg")
    assert store.add("", jpeg())["name"] == "capture.jpg"
    with pytest.raises(CaptureError) as refused:
        store.add("notes.txt", b"plain text")
    assert refused.value.status == 415
    with pytest.raises(CaptureError) as gone:
        store.take([held["file"], "nope"])
    assert gone.value.status == 410


def test_build_upload_keeps_one_file_and_binds_several_images_into_one_pdf():
    red, blue = jpeg("red"), jpeg("blue", (80, 60))
    single = {"name": "image.jpg", "data": red, "mime": "image/jpeg", "pages": 1}
    assert inbox.build_upload([single]) == ("image.jpg", red, "image/jpeg", 1)
    name, data, mime, pages = inbox.build_upload(
        [single, {"name": "image (1).jpg", "data": blue, "mime": "image/jpeg", "pages": 1}])
    assert (name, mime, pages) == ("image.pdf", "application/pdf", 2)
    assert red in data and blue in data
    assert len(pdfium.PdfDocument(data)) == 2
    with pytest.raises(CaptureError):
        inbox.build_upload([single, {"name": "a.pdf", "data": b"%PDF-", "mime": "application/pdf", "pages": 3}])


def test_capture_uploads_with_title_tags_platform_and_link(conn):
    paperless, store = FakePaperless(), inbox.FileStore()
    ids = [store.add("image.jpg", jpeg())["file"]]
    row = asyncio.run(inbox.capture(paperless, conn, CFG, store, ids, title="", link=LINK, details=DETAILS,
                                    note="  POA for PL Grund ", transcribe=False))
    upload = paperless.uploads[0]
    assert (upload["filename"], upload["mime"]) == ("image.jpg", "image/jpeg")
    assert upload["title"] == "Miscellaneous record, Vol. K, 1919-1927, image 32"
    assert (upload["tags"], upload["correspondent"], upload["custom_fields"]) == ([10], 2, {4: LINK})
    assert row["state"] == "processing" and row["details"]["platform"] == "FamilySearch"
    assert inbox.get_capture(conn, row["id"])["note"] == "POA for PL Grund"
    with pytest.raises(CaptureError):
        store.take(ids)


def test_capture_adds_the_ocr_tag_and_refuses_an_empty_card(conn):
    paperless, store = FakePaperless(), inbox.FileStore()
    ids = [store.add("image.jpg", jpeg())["file"]]
    asyncio.run(inbox.capture(paperless, conn, CFG, store, ids, title="POA", link="", details={}, note="",
                              transcribe=True))
    assert paperless.uploads[0]["tags"] == [10, 30]
    assert paperless.uploads[0]["custom_fields"] is None and paperless.uploads[0]["correspondent"] is None
    with pytest.raises(CaptureError):
        asyncio.run(inbox.capture(paperless, conn, CFG, store, [], title="", link="", details={}, note="",
                                  transcribe=False))


def test_capture_refuses_a_file_paperless_already_has(conn):
    paperless, store = FakePaperless(same=[{"id": 21, "title": "Duplicate test 1"}]), inbox.FileStore()
    ids = [store.add("image.jpg", jpeg())["file"]]
    with pytest.raises(CaptureError) as known:
        asyncio.run(inbox.capture(paperless, conn, CFG, store, ids, title="", link="", details={}, note="",
                                  transcribe=False))
    assert (known.value.status, str(known.value)) == (409, "Already in Paperless as #21: Duplicate test 1")
    assert not paperless.uploads and store.take(ids)


def fake_sync(gramps_id):
    async def sync(*_args, **_kwargs):
        if gramps_id:
            yield SyncEvent(kind="item", entity="doc", action="created", source_id="41", gramps_id=gramps_id)
        else:
            yield SyncEvent(kind="item", entity="doc", action="failed", source_id="41", detail="Gramps is down")
        yield SyncEvent(kind="summary", data={})
    return sync


def test_advance_files_the_note_and_syncs_to_gramps(conn, monkeypatch):
    monkeypatch.setattr(routes, "CONSUME_POLL_S", 0)
    monkeypatch.setattr(routes.sync_paperless, "sync", fake_sync("ABC123"))
    paperless = FakePaperless(task={"status": "SUCCESS", "related_document": "41"})
    cid = saved(conn)
    asyncio.run(routes._advance(state_of(paperless, conn), cid))
    row = inbox.get_capture(conn, cid)
    assert (row["state"], row["doc_id"], row["gramps_id"], row["error"]) == ("synced", 41, "ABC123", None)
    assert paperless.notes == [(41, f"Power of attorney section for PL Grund.\n\n{CRUMB}\n"
                                    f"DGS 005537573, image 32 of 644\n{LINK}")]


def test_advance_keeps_a_capture_that_gramps_did_not_take_for_another_try(conn, monkeypatch):
    monkeypatch.setattr(routes, "CONSUME_POLL_S", 0)
    monkeypatch.setattr(routes.sync_paperless, "sync", fake_sync(""))
    cid = saved(conn)
    asyncio.run(routes._advance(state_of(FakePaperless(task={"status": "SUCCESS", "related_document": "41"}), conn), cid))
    row = inbox.get_capture(conn, cid)
    assert (row["state"], row["error"]) == ("filed", "Not in Gramps yet: Gramps is down")


def test_advance_marks_a_duplicate_as_failed(conn, monkeypatch):
    monkeypatch.setattr(routes, "CONSUME_POLL_S", 0)
    task = {"status": "FAILURE", "result": "Not consuming image.jpg: It is a duplicate of Old deed (#12)."}
    cid = saved(conn)
    asyncio.run(routes._advance(state_of(FakePaperless(task=task), conn), cid))
    row = inbox.get_capture(conn, cid)
    assert (row["state"], row["error"], row["doc_id"]) == ("failed", "Already in Paperless as #12", None)
    assert inbox.remove_capture(conn, cid) and inbox.get_capture(conn, cid) is None


def test_advance_transcribes_when_asked_and_reports_a_failure(conn, monkeypatch):
    monkeypatch.setattr(routes, "CONSUME_POLL_S", 0)
    monkeypatch.setattr(routes.sync_paperless, "sync", fake_sync("ABC123"))
    asked = []

    async def ocr(*_args, selected=None):
        asked.append(selected)
        yield SyncEvent(kind="error", detail="no Gemini API key configured")
        yield SyncEvent(kind="summary", data={})

    monkeypatch.setattr(routes.ocr, "run_with_sync", ocr)
    cid = saved(conn, transcribe=True)
    asyncio.run(routes._advance(state_of(FakePaperless(task={"status": "SUCCESS", "related_document": "41"}), conn), cid))
    row = inbox.get_capture(conn, cid)
    assert asked == [{"doc:41"}]
    assert (row["state"], row["error"]) == ("synced", "Transcription failed: no Gemini API key configured")


def test_listing_drops_cited_captures_and_adds_older_uncited_documents(conn):
    cited, waiting = saved(conn), saved(conn)
    inbox.update_capture(conn, cited, state="synced", doc_id=41, gramps_id="ABC123")
    inbox.update_capture(conn, waiting, state="synced", doc_id=42, gramps_id="DEF456")
    docs = [{"id": 41, "title": "POA", "custom_fields": [{"field": 1, "value": "ABC123"}]},
            {"id": 50, "title": "Old deed", "custom_fields": [{"field": 1, "value": "zzz999"}]},
            {"id": 51, "title": "Hidden", "custom_fields": [{"field": 1, "value": "QQQ111"}]},
            {"id": 52, "title": "Cited", "custom_fields": [{"field": 1, "value": "CIT222"}]}]
    inbox.hide_doc(conn, 51)
    st = state_of(FakePaperless(docs=docs), conn, FakeGramps(cited={"ABC123", "CIT222"}))
    request = SimpleNamespace(app=SimpleNamespace(state=st))
    first = asyncio.run(routes.listing(request))["items"]
    assert [r["id"] for r in first] == [waiting]
    assert inbox.get_capture(conn, cited)["cited_at"]
    items = asyncio.run(routes.listing(request, older=True))["items"]
    assert [(r["key"], r["pid"]) for r in items] == [(f"capture:{waiting}", "DEF456"), ("doc:50", "ZZZ999")]
    assert items[1]["older"] and items[1]["title"] == "Old deed"
