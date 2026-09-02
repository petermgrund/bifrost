"""OCR scan and apply"""

import asyncio

import pytest

from bifrost.core import db
from bifrost.core.config import GeminiConfig, SyncPaperlessConfig
from bifrost.modules import ocr

CFG = SyncPaperlessConfig(ocr_tag="Gemini OCR", transcription_tag_id=9,
                          gramps_id_field_id=1, gramps_url_field_id=2)
GEM = GeminiConfig(model="gemini-test")


class FakePaperless:
    def __init__(self, docs):
        self.docs = docs
        self.patched = {}
        self.tags_set = {}

    async def resolve_tag_id(self, name):
        return 5 if name == "Gemini OCR" else None

    async def list_documents_by_tag(self, tag_id):
        return self.docs

    async def download_original(self, doc_id):
        return b"not really a pdf", "application/pdf"

    async def patch_content(self, doc_id, content):
        self.patched[doc_id] = content
        for d in self.docs:
            if d["id"] == doc_id:
                d["content"] = content

    async def patch_tags(self, doc_id, tag_ids):
        self.tags_set[doc_id] = tag_ids


class FakeGemini:
    configured = True

    def __init__(self):
        self.calls = []

    async def transcribe(self, data, mime, prompt, thinking_budget):
        self.calls.append(mime)
        return "Transcribed text"


class NoGramps:
    """Raises on any Gramps call"""

    def __getattr__(self, name):
        raise AssertionError(f"Gramps touched via {name}")


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


def _docs():
    return [{"id": 1, "title": "One", "content": "abc", "tags": [5],
             "custom_fields": [{"field": 1, "value": "ABC123"}]},
            {"id": 2, "title": "Two", "content": "", "tags": [5, 9], "custom_fields": []},
            {"id": 3, "title": "Dash", "content": " - ", "tags": [5], "custom_fields": []}]


def _events(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


def _rows(events):
    return [e for e in events if e.kind == "item"]


def test_scan_lists_every_tagged_doc_as_create_or_replace(conn):
    rows = _rows(_events(ocr.run(FakePaperless(_docs()), FakeGemini(), conn, CFG, GEM, apply=False)))
    assert [(e.source_id, e.action) for e in rows] == [
        ("1", "would_replace"), ("2", "would_create"), ("3", "would_create")]
    assert rows[0].data["cols"] == {"current text": "3 chars"}
    assert rows[1].data is None
    assert rows[0].gramps_id == "ABC123" and rows[1].gramps_id is None


def test_selected_limits_an_apply_and_transcribed_docs_stay_listed(conn):
    pl, gem = FakePaperless(_docs()), FakeGemini()
    events = _events(ocr.run(pl, gem, conn, CFG, GEM, apply=True, selected={"doc:2", "doc:1"}))
    assert sorted(pl.patched) == [1, 2] and gem.calls == ["application/pdf"] * 2
    assert [(e.source_id, e.action) for e in _rows(events)] == [("1", "replaced"), ("2", "created")]
    assert _rows(events)[0].data["cols"]["new text"] == "16 chars"
    assert _rows(events)[1].data["cols"]["transcription tag"] == "already set"
    assert events[-1].data == {"transcribed": 1, "replaced": 1, "errors": 0}
    rows = _rows(_events(ocr.run(pl, gem, conn, CFG, GEM, apply=False)))
    assert [e.source_id for e in rows] == ["1", "2", "3"]
    assert rows[1].action == "would_replace"
    assert rows[1].data["cols"]["transcribed"].endswith("(gemini-test)")


def test_run_with_sync_skips_the_note_sync_when_nothing_was_transcribed(conn):
    events = _events(ocr.run_with_sync(FakePaperless(_docs()), NoGramps(), FakeGemini(), conn,
                                       CFG, GEM, selected=set()))
    assert [e.kind for e in events] == ["started", "summary"]
    assert events[-1].data == {"transcribed": 0, "replaced": 0, "errors": 0}


def test_run_without_gemini_key_is_an_error_event(conn):
    class Unconfigured(FakeGemini):
        configured = False

    events = _events(ocr.run(FakePaperless(_docs()), Unconfigured(), conn, CFG, GEM, apply=True))
    assert events[0].kind == "error" and "Gemini" in events[0].detail
