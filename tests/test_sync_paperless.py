import asyncio

from bifrost.core import db
from bifrost.core.config import SyncPaperlessConfig
from bifrost.modules import sync_paperless
from bifrost.modules.sync_paperless import (
    TRANSLATION_DELIMITER,
    build_gramps_date,
    dates_equal,
    format_gramps_date,
    split_transcription,
)


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


class _FakePaperless:
    def __init__(self, docs):
        self._docs = docs

    async def resolve_tag_id(self, name):
        return {"doc": 1, "img": 2}.get(name)

    async def list_documents_by_tags(self, tag_ids):
        return list(self._docs)

    async def get_document_metadata(self, doc_id):
        return {"media_filename": f"{doc_id:07d}.pdf", "original_checksum": "abc"}


class _FakeGramps:
    async def list_media_gramps_ids(self):
        return set()


def test_selected_keys_filter_rows(tmp_path):
    import asyncio

    from bifrost.core import db
    from bifrost.core.config import SyncPaperlessConfig
    from bifrost.modules.sync_paperless import sync

    docs = [{"id": 1, "title": "One", "custom_fields": [], "tags": [1]},
            {"id": 2, "title": "Two", "custom_fields": [], "tags": [1]}]
    cfg = SyncPaperlessConfig(gramps_id_field_id=10, gramps_url_field_id=11)
    conn = db.connect(tmp_path / "t.db")

    async def collect():
        return [e async for e in sync(_FakePaperless(docs), _FakeGramps(), conn,
                                      cfg, apply=False, selected={"doc:2"})]

    events = asyncio.run(collect())
    items = [(e.action, e.source_id) for e in events if e.kind == "item"]
    assert items == [("would_create", "2")]
    summary = next(e for e in events if e.kind == "summary")
    assert summary.data["created"] == 1


def test_clients_follow_redirects():
    from bifrost.core.clients import GrampsClient, PaperlessClient
    g = GrampsClient("http://x/api", "u", "p")
    p = PaperlessClient("http://x", "t")
    assert g._client.follow_redirects
    assert p._client.follow_redirects



class TestProgressBands:

    class Paperless:
        async def resolve_tag_id(self, name):
            return 1 if name == "doc" else None

        async def list_documents_by_tags(self, ids):
            return [{"id": 7, "title": "Doc", "custom_fields": [], "tags": []}]

        async def get_document_metadata(self, doc_id):
            return {"media_filename": "a.pdf", "original_checksum": "c"}

        @staticmethod
        def custom_field_value(doc, fid):
            return None

    class Gramps:
        async def list_media_gramps_ids(self):
            return set()

        async def get_tag_handle(self, name):
            return None

    def _progress(self, tmp_path, **kw):
        conn = db.connect(tmp_path / "p.db")
        cfg = SyncPaperlessConfig(sync_tags=("doc",), gramps_id_field_id=1,
                                  gramps_url_field_id=2)

        async def collect():
            return [e async for e in sync_paperless.sync(
                self.Paperless(), self.Gramps(), conn, cfg, apply=False, **kw)]
        events = asyncio.run(collect())
        conn.close()
        return [e for e in events if e.kind == "progress"]

    def test_progress_names_its_band_and_the_band_count(self, tmp_path):
        progress = self._progress(tmp_path)
        assert progress, "expected progress events"
        assert progress[0].data["band_index"] == 0
        assert progress[0].data["band_count"] == 2
        assert {e.data["band_index"] for e in progress} == {0, 1}
        assert {e.detail for e in progress} == {
            "Checking versions", "Checking titles and dates"}

    def test_versions_only_run_has_a_single_band(self, tmp_path):
        progress = self._progress(tmp_path, versions_only=True)
        assert all(e.data["band_count"] == 1 for e in progress)
