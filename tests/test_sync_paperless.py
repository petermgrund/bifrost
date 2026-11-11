import asyncio
import copy
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core.clients.gramps import GrampsClient
from bifrost.core.clients.paperless import PaperlessError
from bifrost.core.config import GeminiConfig, SyncPaperlessConfig
from bifrost.modules import sync_paperless
from bifrost.modules.sync_paperless import (
    TRANSLATION_DELIMITER,
    build_gramps_date,
    dates_equal,
    format_gramps_date,
    split_transcription,
)
from bifrost.web.routes import sync as sync_routes


def _doc(created="1947-03-12", doc_id=42):
    return {"id": doc_id, "created": created, "title": "Test doc"}


def test_date_optin_requires_qualifier():
    assert build_gramps_date(_doc(), None) is None


def test_date_exact():
    d = build_gramps_date(_doc(), "Exact")
    assert d["dateval"] == [12, 3, 1947, False]
    assert d["modifier"] == 0 and d["quality"] == 0
    assert format_gramps_date(d) == "1947-03-12"


def test_date_circa():
    d = build_gramps_date(_doc(), "Circa")
    assert d["modifier"] == 3
    assert d["dateval"] == [12, 3, 1947, False]
    assert format_gramps_date(d) == "About 1947-03-12"


def test_date_before_after():
    assert build_gramps_date(_doc(), "Before")["modifier"] == 1
    assert build_gramps_date(_doc(), "After")["modifier"] == 2


def test_date_year_only():
    d = build_gramps_date(_doc(), "Year only")
    assert d["dateval"] == [0, 0, 1947, False]
    assert format_gramps_date(d) == "1947"


def test_date_decade_rounds_down_and_estimates():
    d = build_gramps_date(_doc(), "Decade only")
    assert d["dateval"] == [0, 0, 1940, False]
    assert d["quality"] == 1
    assert format_gramps_date(d) == "Est. 1940"


def test_date_to_from_and_unknown_skip():
    assert build_gramps_date(_doc(), "To/from") is None
    assert build_gramps_date(_doc(), "Sometime") is None


def test_date_missing_created():
    assert build_gramps_date({"id": 1}, "Exact") is None


def test_dates_equal():
    a = {"dateval": [1, 2, 1900, False], "modifier": 0, "quality": 0}
    assert dates_equal(a, dict(a))
    assert not dates_equal(a, {**a, "modifier": 3})
    assert dates_equal(None, {})
    assert not dates_equal(a, None)


def test_split_transcription_no_delimiter():
    assert split_transcription("Kära Maria, ...") == ("Kära Maria, ...", None)


def test_split_transcription_with_translation():
    content = f"Kära Maria\n\n{TRANSLATION_DELIMITER}\n\nDear Maria"
    tx, tl = split_transcription(content)
    assert tx == "Kära Maria"
    assert tl == "Dear Maria"


def test_split_transcription_empty_translation():
    tx, tl = split_transcription(f"Text\n{TRANSLATION_DELIMITER}\n  ")
    assert tx == "Text"
    assert tl is None


# ---- fakes

DOC_TAG, IMG_TAG, TX_TAG, OCR_TAG = 1, 2, 43, 5
CFG = SyncPaperlessConfig(sync_tags=("doc", "img"), gramps_id_field_id=12, gramps_url_field_id=14,
                          transcription_tag_id=TX_TAG, public_url="http://p",
                          gramps_public_url="http://g")


class Paperless:
    def __init__(self, docs, missing=()):
        self.docs = docs
        self.calls = []
        self.missing = set(missing)
        self.metadata = {}
        self.gate = None
        self.fields = {}
        self.content = {}
        self.tags = {}

    async def resolve_tag_id(self, name):
        return {"doc": DOC_TAG, "img": IMG_TAG, "Gemini OCR": OCR_TAG}.get(name)

    async def list_documents_by_tags(self, ids):
        self.calls.append("list")
        return [d for d in self.docs if set(ids) & set(d.get("tags", []))]

    async def list_documents_by_tag(self, tag_id):
        self.calls.append("list_tx")
        return [d for d in self.docs if tag_id in d.get("tags", [])]

    async def get_document(self, doc_id):
        self.calls.append(("get", doc_id))
        if self.gate is not None:
            await self.gate.wait()
        if doc_id in self.missing:
            raise PaperlessError(f"GET /api/documents/{doc_id}/ → 404", 404)
        return copy.deepcopy(next(d for d in self.docs if d["id"] == doc_id))

    async def get_document_metadata(self, doc_id):
        return self.metadata.get(doc_id) or {"media_filename": f"{doc_id:07d}.pdf", "original_checksum": "c"}

    async def patch_custom_fields(self, doc_id, cfs):
        self.fields[doc_id] = cfs
        for d in self.docs:
            if d["id"] == doc_id:
                d["custom_fields"] = cfs

    async def resolve_custom_field_options(self, fid):
        return {}

    async def download_original(self, doc_id):
        return b"%PDF-1.4", "application/pdf"

    async def patch_content(self, doc_id, content):
        self.content[doc_id] = content
        for d in self.docs:
            if d["id"] == doc_id:
                d["content"] = content

    async def patch_tags(self, doc_id, tag_ids):
        self.tags[doc_id] = tag_ids
        for d in self.docs:
            if d["id"] == doc_id:
                d["tags"] = list(tag_ids)


class Gramps:
    def __init__(self, media=None, withdrawn=""):
        self.media = media or {}
        self.notes = {}
        self.withdrawn = withdrawn
        self.created = []
        self.updated = []
        self.updated_notes = []
        self.listings = 0
        self.unreadable = set()

    async def list_media_gramps_ids(self):
        self.listings += 1
        return set(self.media)

    async def find_notes(self, note_type):
        if not self.withdrawn:
            return []
        return [{"handle": "wn", "gramps_id": "N0001", "type": note_type, "text": {"string": self.withdrawn}}]

    async def create_media(self, obj):
        self.media[obj["gramps_id"]] = obj
        self.created.append(obj)

    async def get_media_by_gramps_id(self, gid, backlinks=False, notes=False):
        found = self.media.get(gid)
        if found is None:
            return None
        found = copy.deepcopy(found)
        if notes:
            found["extended"] = {"notes": [self.notes[h] for h in found.get("note_list") or [] if h in self.notes]}
        return found

    async def update_media(self, handle, obj):
        self.updated.append(obj)
        self.media[obj["gramps_id"]] = obj

    async def media_md5(self, handle):
        media = next((m for m in self.media.values() if m.get("handle") == handle), None)
        if media and media.get("path") in self.unreadable:
            raise RuntimeError("404 file not found")
        return f"md5-{handle}"

    store_checksum = GrampsClient.store_checksum

    async def get_tag_handle(self, name):
        return None

    async def _paged(self, path, keys=None):
        return [{"gramps_id": n["gramps_id"]} for n in self.notes.values()]

    async def create_note(self, obj):
        self.notes[obj["handle"]] = obj

    async def update_note(self, handle, obj):
        self.notes[handle] = obj
        self.updated_notes.append(obj)

    async def get_media_backlinks(self, handle):
        return {}


def synced(gramps, doc_id=1, gid="DOC111", title="Letter", tags=(DOC_TAG,), content=None, notes=()):
    """A document already in Gramps, with the notes it has"""
    media = {"gramps_id": gid, "handle": f"h-{gid}", "desc": title, "path": f"paperless/{doc_id:07d}.pdf",
             "mime": "application/pdf", "checksum": f"md5-h-{gid}", "note_list": [],
             "attribute_list": [{"type": "Paperless ID", "value": str(doc_id)}]}
    for handle, kind, text in notes:
        gramps.notes[handle] = {"handle": handle, "gramps_id": f"N{len(gramps.notes) + 1:04d}", "type": kind,
                                "text": {"string": text}}
        media["note_list"].append(handle)
    gramps.media[gid] = media
    doc = {"id": doc_id, "title": title, "tags": list(tags), "custom_fields": [{"field": 12, "value": gid}]}
    if content is not None:
        doc["content"] = content
    return doc


def run(paperless, gramps, apply=True, cfg=CFG, **kw):
    async def collect():
        return [e async for e in sync_paperless.sync(paperless, gramps, cfg, apply=apply, **kw)]
    return asyncio.run(collect())


def items(events, entity=None):
    return [e for e in events if e.kind == "item" and (entity is None or e.entity == entity)]


def summary(events):
    return next(e for e in events if e.kind == "summary").data


def note_types(gramps, gid):
    return sorted(gramps.notes[h]["type"] for h in gramps.media[gid]["note_list"])


# ---- creating

class TestCreate:

    def test_a_tagged_document_gets_a_code_the_fields_and_a_checksum(self):
        gramps = Gramps()
        paperless = Paperless([{"id": 3, "title": "New", "tags": [DOC_TAG], "custom_fields": []}])
        events = run(paperless, gramps)
        (created,) = items(events)
        assert created.action == "created" and created.source_id == "3"
        media = gramps.media[created.gramps_id]
        assert (media["desc"], media["path"], media["mime"]) == ("New", "paperless/0000003.pdf", "application/pdf")
        assert media["checksum"] == f"md5-{media['handle']}"
        assert [(a["type"], a["value"]) for a in media["attribute_list"]] == [
            ("Paperless URL", "http://p/documents/3/details"), ("Paperless ID", "3")]
        assert paperless.fields[3] == [{"field": 12, "value": created.gramps_id},
                                       {"field": 14, "value": f"http://g/media/{created.gramps_id}"}]
        assert summary(events)["created"] == 1

    def test_preview_writes_nothing(self):
        gramps = Gramps()
        paperless = Paperless([{"id": 3, "title": "New", "tags": [DOC_TAG], "custom_fields": []}])
        events = run(paperless, gramps, apply=False)
        assert [e.action for e in items(events)] == ["would_create"]
        assert gramps.media == {} and paperless.fields == {} and gramps.listings == 0

    def test_a_new_code_avoids_live_withdrawn_and_paperless_field_codes(self, script_ids):
        gramps = Gramps(withdrawn="WDRN22 2026-01-01 lost")
        synced(gramps, doc_id=1, gid="MNTD22")
        docs = [{"id": 1, "title": "Synced", "tags": [DOC_TAG], "custom_fields": [{"field": 12, "value": "MNTD22"}]},
                {"id": 3, "title": "New", "tags": [DOC_TAG], "custom_fields": []},
                {"id": 2, "title": "Typed", "tags": [DOC_TAG], "custom_fields": [{"field": 12, "value": "PPRK22"}]}]
        script_ids("MNTD22", "WDRN22", "PPRK22", "FRESH2")
        events = run(Paperless(docs), gramps)
        created = {e.source_id: e.gramps_id for e in items(events) if e.action == "created"}
        assert created == {"2": "PPRK22", "3": "FRESH2"}

    def test_a_code_typed_into_the_field_is_used(self):
        gramps = Gramps()
        doc = {"id": 2, "title": "Typed", "tags": [DOC_TAG], "custom_fields": [{"field": 12, "value": " pprk-22 "}]}
        events = run(Paperless([doc]), gramps)
        (created,) = items(events)
        assert created.gramps_id == "PPRK22" and "PPRK22" in gramps.media
        assert [cf["value"] for cf in doc["custom_fields"]] == ["PPRK22", "http://g/media/PPRK22"]

    @pytest.mark.parametrize("code,msg", [("WDRN22", "withdrawn on 2026-01-01"), ("ABCDEI", "contains I"),
                                          ("TYPED2", "Paperless document 9")])
    def test_a_typed_code_that_may_not_be_used_is_a_failed_row(self, code, msg):
        gramps = Gramps(withdrawn="WDRN22 2026-01-01 lost")
        docs = [{"id": 2, "title": "Typed", "tags": [DOC_TAG], "custom_fields": [{"field": 12, "value": code}]},
                {"id": 9, "title": "Other", "tags": [DOC_TAG], "custom_fields": [{"field": 12, "value": "TYPED2"}]}]
        events = run(Paperless(docs[:1] + (docs[1:] if code == "TYPED2" else [])), gramps)
        failed = [e for e in items(events) if e.action == "failed" and e.source_id == "2"]
        assert len(failed) == 1 and msg in failed[0].detail
        assert code not in gramps.media and summary(events)["errors"] >= 1

    def test_a_file_gramps_cannot_read_is_a_failed_row(self):
        gramps = Gramps()
        gramps.unreadable.add("paperless/0000003.pdf")
        events = run(Paperless([{"id": 3, "title": "New", "tags": [DOC_TAG], "custom_fields": []}]), gramps)
        assert [e.action for e in items(events)] == ["created", "failed"]
        assert "could not read its file" in items(events)[1].detail

    def test_selected_keys_limit_an_apply(self):
        docs = [{"id": 1, "title": "One", "custom_fields": [], "tags": [DOC_TAG]},
                {"id": 2, "title": "Two", "custom_fields": [], "tags": [DOC_TAG]}]
        gramps = Gramps()
        events = run(Paperless(docs), gramps, selected={"doc:2"})
        assert [(e.action, e.source_id) for e in items(events)] == [("created", "2")]
        assert summary(events)["created"] == 1 and len(gramps.media) == 1


# ---- documents already in Gramps

class TestUpdate:

    def test_an_unchanged_document_is_quiet(self):
        gramps = Gramps()
        events = run(Paperless([synced(gramps)]), gramps)
        assert items(events) == [] and gramps.updated == []
        assert summary(events)["skipped"] == 0 and summary(events)["created"] == 0

    def test_a_new_paperless_version_repoints_the_file_and_refreshes_the_checksum(self):
        gramps = Gramps()
        paperless = Paperless([synced(gramps)])
        paperless.metadata[1] = {"media_filename": "0000001_v2.pdf", "original_checksum": "v2"}
        preview = run(paperless, gramps, apply=False)
        assert [e.data["cols"] for e in items(preview)] == [
            {"version": "paperless/0000001.pdf → paperless/0000001_v2.pdf"}]
        events = run(paperless, gramps)
        (ev,) = items(events)
        assert ev.action == "updated" and ev.data["cols"]["checksum"] == "updated"
        media = gramps.media["DOC111"]
        assert (media["path"], media["checksum"]) == ("paperless/0000001_v2.pdf", "md5-h-DOC111")
        assert summary(events)["versions_updated"] == 1
        assert items(run(paperless, gramps)) == []

    def test_an_unreadable_new_version_is_retried_on_the_next_run(self):
        gramps = Gramps()
        paperless = Paperless([synced(gramps)])
        paperless.metadata[1] = {"media_filename": "0000001_v2.pdf", "original_checksum": "v2"}
        gramps.unreadable.add("paperless/0000001_v2.pdf")
        events = run(paperless, gramps)
        assert [e.action for e in items(events)] == ["failed"]
        assert gramps.media["DOC111"]["checksum"] == ""
        gramps.unreadable.clear()
        events = run(paperless, gramps)
        assert [e.data["cols"] for e in items(events)] == [{"checksum": "missing"}]
        assert gramps.media["DOC111"]["checksum"] == "md5-h-DOC111"

    def test_the_title_follows_paperless(self):
        gramps = Gramps()
        doc = synced(gramps)
        doc["title"] = "Letter, 1931"
        events = run(Paperless([doc]), gramps)
        (ev,) = items(events, "media")
        assert ev.data["cols"] == {"title": "'Letter' → 'Letter, 1931'"}
        assert gramps.media["DOC111"]["desc"] == "Letter, 1931" and summary(events)["titles_updated"] == 1

    def test_progress_events_bracket_the_run(self):
        gramps = Gramps()
        events = run(Paperless([synced(gramps), synced(gramps, doc_id=2, gid="DOC222")]), gramps)
        progress = [e for e in events if e.kind == "progress"]
        assert {e.detail for e in progress} == {"Checking documents"}
        assert progress[0].data["done"] == 0 and progress[-1].data == {"done": 2, "total": 2, "percent": 100}


# ---- transcriptions

class TestTranscriptions:

    def test_a_new_document_gets_its_transcription_and_translation(self):
        gramps = Gramps()
        doc = {"id": 1133, "title": "Death index", "custom_fields": [], "tags": [DOC_TAG, TX_TAG],
               "content": f"Siggerud\n{TRANSLATION_DELIMITER}\nSiggerud (en)"}
        events = run(Paperless([doc]), gramps)
        assert [(e.entity, e.action) for e in items(events)] == [("doc", "created"), ("note", "created")]
        assert items(events)[0].data["cols"] == {"transcription": "new", "translation": "new"}
        (media,) = gramps.media.values()
        assert note_types(gramps, media["gramps_id"]) == ["Transcription", "Translation"]
        assert summary(events)["created"] == 1 and summary(events)["tx_created"] == 1

    def test_notes_that_match_the_text_are_left_alone(self):
        gramps = Gramps()
        doc = synced(gramps, tags=(DOC_TAG, TX_TAG), content=" Kära Maria ",
                     notes=[("n-tx", "Transcription", "Kära Maria")])
        events = run(Paperless([doc]), gramps)
        assert items(events) == [] and gramps.updated == [] and gramps.updated_notes == []

    def test_changed_text_rewrites_the_note_and_a_new_translation_is_added(self):
        gramps = Gramps()
        doc = synced(gramps, tags=(DOC_TAG, TX_TAG), content=f"Kära mor\n{TRANSLATION_DELIMITER}\nDear mother",
                     notes=[("n-tx", "Transcription", "Kära Maria")])
        preview = run(Paperless([doc]), gramps, apply=False)
        assert [(e.action, e.data["cols"]) for e in items(preview)] == [
            ("would_update", {"transcription": "modified", "translation": "new"})]
        events = run(Paperless([doc]), gramps)
        assert [e.action for e in items(events)] == ["updated"]
        assert gramps.notes["n-tx"]["text"]["string"] == "Kära mor"
        assert note_types(gramps, "DOC111") == ["Transcription", "Translation"]
        assert summary(events)["tx_updated"] == 1

    def test_a_transcription_tagged_document_without_a_sync_tag_still_gets_notes(self):
        gramps = Gramps()
        doc = synced(gramps, tags=(TX_TAG,), content="Text")
        events = run(Paperless([doc]), gramps)
        assert [(e.entity, e.action) for e in items(events)] == [("note", "created")]
        assert note_types(gramps, "DOC111") == ["Transcription"]

    def test_no_text_yet_is_announced_at_creation(self):
        doc = {"id": 5, "title": "Scan", "custom_fields": [], "tags": [DOC_TAG, TX_TAG], "content": ""}
        events = run(Paperless([doc]), Gramps(), apply=False)
        assert items(events)[0].data["cols"] == {"transcription": "tagged, no text yet"}


# ---- one document at a time

class TestDocIds:

    def test_the_documents_are_fetched_and_nothing_listed(self):
        gramps = Gramps()
        docs = [synced(gramps), {"id": 2, "title": "Other", "tags": [DOC_TAG], "custom_fields": []}]
        paperless = Paperless(docs)
        events = run(paperless, gramps, doc_ids=[1])
        assert paperless.calls == [("get", 1)] and gramps.listings == 0
        assert items(events) == [] and summary(events)["created"] == 0

    def test_a_tagged_document_without_an_id_is_created(self):
        gramps = Gramps()
        paperless = Paperless([{"id": 3, "title": "New", "tags": [DOC_TAG], "custom_fields": []}])
        events = run(paperless, gramps, doc_ids=[3])
        assert [e.source_id for e in items(events) if e.action == "created"] == ["3"]
        assert paperless.calls == [("get", 3)] and gramps.listings == 1

    def test_a_document_without_a_tag_is_left_alone(self):
        gramps = Gramps()
        paperless = Paperless([{"id": 5, "title": "Receipt", "tags": [9], "custom_fields": []}])
        events = run(paperless, gramps, doc_ids=[5])
        assert [e.detail for e in events if e.kind == "started"] == ["document #5 is not tagged for Gramps"]
        assert not any(summary(events).values()) and not gramps.media

    def test_a_missing_document_is_an_error_event(self):
        events = run(Paperless([], missing={7}), Gramps(), doc_ids=[7])
        assert [e.kind for e in events] == ["error", "summary"]
        assert events[0].source_id == "7" and "not found" in events[0].detail

    def test_other_paperless_errors_still_raise(self):
        class Down(Paperless):
            async def get_document(self, doc_id):
                raise PaperlessError("GET /api/documents/7/ → 502", 502)

        with pytest.raises(PaperlessError):
            run(Down([]), Gramps(), doc_ids=[7])

    def test_a_document_created_this_run_gets_its_transcription(self):
        gramps = Gramps()
        doc = {"id": 1133, "title": "Death index", "custom_fields": [], "tags": [DOC_TAG, TX_TAG],
               "content": "Siggerud"}
        paperless = Paperless([doc])
        events = run(paperless, gramps, doc_ids=[1133])
        assert summary(events)["created"] == 1 and summary(events)["tx_created"] == 1
        assert paperless.calls == [("get", 1133)] and len(gramps.notes) == 1


# ---- the webhook

WEBHOOK = "/sync/api/paperless/webhook"
TOKEN = {"X-Bifrost-Token": "s3cret"}


class FakeGemini:
    configured = True

    async def transcribe(self, data, mime, prompt, thinking_budget):
        return "Transcribed text"


def make_app(paperless, gramps=None, token="s3cret", ocr_tag=""):
    app = FastAPI()
    app.include_router(sync_routes.router)
    app.state.paperless = paperless
    app.state.gramps = gramps or Gramps()
    app.state.gemini = FakeGemini()
    app.state.caches = {}
    app.state.cfg = SimpleNamespace(
        sync_paperless=SyncPaperlessConfig(sync_tags=("doc",), gramps_id_field_id=12, gramps_url_field_id=14,
                                           transcription_tag_id=TX_TAG, webhook_token=token, ocr_tag=ocr_tag),
        gemini=GeminiConfig())
    return app


def call(app, method, url, **kw):
    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://bifrost") as client:
            resp = await client.request(method, url, **kw)
        await asyncio.gather(*getattr(app.state, "webhook_tasks", ()))
        return resp
    return asyncio.run(go())


class TestWebhook:

    def test_off_without_a_token(self):
        paperless = Paperless([])
        r = call(make_app(paperless, token=""), "POST", WEBHOOK, headers=TOKEN, json={"doc_id": "1"})
        assert r.status_code == 404 and paperless.calls == []

    def test_rejects_a_missing_or_wrong_token(self):
        paperless = Paperless([])
        app = make_app(paperless)
        assert call(app, "POST", WEBHOOK, json={"doc_id": "1"}).status_code == 403
        assert call(app, "POST", WEBHOOK, json={"doc_id": "1"},
                    headers={"X-Bifrost-Token": "nope"}).status_code == 403
        assert paperless.calls == []

    @pytest.mark.parametrize("kw", [
        {"json": {"doc_id": "1"}}, {"json": {"id": 1}},
        {"data": {"doc_id": "1"}}, {"params": {"doc_id": "1"}}, {"params": {"id": "1"}},
        {"data": {"doc_id": "1"}, "files": {"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}},
    ])
    def test_queues_the_document_from_json_form_or_query(self, kw):
        gramps = Gramps()
        paperless = Paperless([synced(gramps)])
        r = call(make_app(paperless, gramps), "POST", WEBHOOK, headers=TOKEN, **kw)
        assert r.status_code == 202 and r.json() == {"doc_id": 1, "queued": True}
        assert paperless.calls == [("get", 1)] and gramps.listings == 0

    @pytest.mark.parametrize("kw", [
        {"json": {"doc_id": "abc"}}, {"json": {}}, {}, {"data": {"doc_id": ""}},
        {"params": {"doc_id": "-1"}}, {"json": [1]},
        {"content": b"not json", "headers": {"content-type": "application/json"}},
    ])
    def test_needs_an_integer_id(self, kw):
        paperless = Paperless([])
        headers = {**TOKEN, **kw.get("headers", {})}
        kw = {k: v for k, v in kw.items() if k != "headers"}
        r = call(make_app(paperless), "POST", WEBHOOK, headers=headers, **kw)
        assert r.status_code == 400 and paperless.calls == []

    def test_an_untagged_document_creates_nothing(self):
        gramps = Gramps()
        paperless = Paperless([{"id": 5, "title": "Receipt", "tags": [9], "custom_fields": []}])
        r = call(make_app(paperless, gramps), "POST", WEBHOOK, headers=TOKEN, data={"doc_id": "5"})
        assert r.status_code == 202
        assert paperless.calls == [("get", 5)] and not gramps.media and gramps.listings == 0

    def test_repoints_media_at_the_version_selected_in_paperless(self):
        gramps = Gramps()
        paperless = Paperless([synced(gramps)])
        paperless.metadata[1] = {"media_filename": "0000001_v2.pdf", "original_checksum": "v2"}
        r = call(make_app(paperless, gramps), "POST", WEBHOOK, headers=TOKEN, data={"doc_id": "1"})
        assert r.status_code == 202
        media = gramps.media["DOC111"]
        assert (media["path"], media["checksum"]) == ("paperless/0000001_v2.pdf", "md5-h-DOC111")
        assert paperless.calls == [("get", 1)] and gramps.listings == 0

    def test_an_ocr_tagged_document_is_transcribed_and_gets_its_notes(self):
        gramps = Gramps()
        doc = {"id": 8, "title": "Scan", "tags": [DOC_TAG, OCR_TAG], "custom_fields": [], "content": ""}
        paperless = Paperless([doc])
        r = call(make_app(paperless, gramps, ocr_tag="Gemini OCR"), "POST", WEBHOOK, headers=TOKEN,
                 json={"doc_id": 8})
        assert r.status_code == 202
        assert paperless.content == {8: "Transcribed text"} and paperless.tags == {8: [DOC_TAG, TX_TAG]}
        (media,) = gramps.media.values()
        assert note_types(gramps, media["gramps_id"]) == ["Transcription"]
        assert [c for c in paperless.calls if c != "list_tx"] == [("get", 8), ("get", 8), ("get", 8)]

    def test_a_document_without_the_ocr_tag_is_not_sent_to_gemini(self):
        gramps = Gramps()
        paperless = Paperless([synced(gramps)])
        call(make_app(paperless, gramps, ocr_tag="Gemini OCR"), "POST", WEBHOOK, headers=TOKEN, json={"doc_id": 1})
        assert paperless.content == {} and paperless.calls == [("get", 1), ("get", 1)]

    def test_answers_before_the_sync_runs_and_runs_one_at_a_time(self):
        docs = [{"id": i, "title": f"Doc {i}", "tags": [9], "custom_fields": []} for i in (1, 2)]
        paperless = Paperless(docs)
        app = make_app(paperless)

        async def settle():
            for _ in range(3):
                await asyncio.sleep(0)

        async def go():
            paperless.gate = asyncio.Event()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://bifrost") as client:
                first = await client.post(WEBHOOK, headers=TOKEN, json={"doc_id": "1"})
                await settle()
                second = await client.post(WEBHOOK, headers=TOKEN, json={"doc_id": "2"})
                await settle()
                calls_before = list(paperless.calls)
                paperless.gate.set()
                await asyncio.gather(*app.state.webhook_tasks)
                await settle()
            return first, second, calls_before

        first, second, calls_before = asyncio.run(go())
        assert first.status_code == second.status_code == 202
        assert calls_before == [("get", 1)]
        assert paperless.calls == [("get", 1), ("get", 2)]
        assert not app.state.webhook_tasks


def test_clients_follow_redirects():
    from bifrost.core.clients import GrampsClient, PaperlessClient
    g = GrampsClient("http://x/api", "u", "p")
    p = PaperlessClient("http://x", "t")
    assert g._client.follow_redirects
    assert p._client.follow_redirects
