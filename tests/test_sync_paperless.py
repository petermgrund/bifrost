import asyncio
import copy

import pytest

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

    def test_progress_is_one_running_count_across_the_passes(self, tmp_path):
        progress = self._progress(tmp_path)
        assert progress, "expected progress events"
        assert len({e.data["total"] for e in progress}) == 1
        dones = [e.data["done"] for e in progress]
        assert dones == sorted(dones) and dones[0] == 0
        assert dones[-1] == progress[-1].data["total"]
        assert {e.detail for e in progress} >= {"Checking new documents", "Checking versions",
                                                "Checking titles and dates"}

    def test_versions_only_run_counts_only_the_version_pass(self, tmp_path):
        progress = self._progress(tmp_path, versions_only=True)
        assert progress and {e.detail for e in progress} == {"Checking versions"}
        assert progress[-1].data["done"] == progress[-1].data["total"]


class TestMinting:

    class Paperless:
        def __init__(self, docs):
            self.docs = docs

        async def resolve_tag_id(self, name):
            return 1 if name == "doc" else None

        async def list_documents_by_tags(self, ids):
            return self.docs

        async def get_document_metadata(self, doc_id):
            return {"media_filename": f"{doc_id:07d}.pdf", "original_checksum": "c"}

        async def patch_custom_fields(self, doc_id, cfs):
            pass

    class Gramps:
        def __init__(self, conn=None):
            self.media = {}
            self.conn = conn

        async def list_media_gramps_ids(self):
            return set(self.media)

        async def create_media(self, obj):
            self.media[obj["gramps_id"]] = obj
            if self.conn is not None:  # another mint registers the same id meanwhile
                self.conn.execute(
                    "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
                    "VALUES (?, 'immich', 'a9', 'Racer', '2026-01-01')", (obj["gramps_id"],))
                self.conn.commit()

        async def get_media_by_gramps_id(self, gid):
            return self.media.get(gid)

        async def get_tag_handle(self, name):
            return None

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "m.db")
        # XJ4DBT: minted, then its media was deleted from Gramps
        c.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES ('XJ4DBT', 'paperless', '101', 'Deleted doc', '2026-01-01')")
        c.execute(
            "INSERT INTO reserved_ids (gramps_id, created_at, assigned_at) VALUES ('RSVD22', 't', 't')")
        c.commit()
        yield c
        c.close()

    def _sync(self, conn, gramps, docs):
        cfg = SyncPaperlessConfig(sync_tags=("doc",), gramps_id_field_id=12, gramps_url_field_id=14)

        async def collect():
            return [e async for e in sync_paperless.sync(
                self.Paperless(docs), gramps, conn, cfg, apply=True)]
        return asyncio.run(collect())

    def test_create_never_reissues_a_deleted_reserved_or_paperless_id(self, conn, script_ids):
        docs = [{"id": 1, "title": "New", "custom_fields": [], "tags": [1]},
                {"id": 2, "title": "Typed by hand", "tags": [1],
                 "custom_fields": [{"field": 12, "value": "PPRK22"}]}]
        script_ids("XJ4DBT", "RSVD22", "PPRK22", "FRESH2")
        gramps = self.Gramps()
        events = self._sync(conn, gramps, docs)
        created = [e for e in events if e.kind == "item" and e.action == "created"]
        assert [(e.source_id, e.gramps_id) for e in created] == [("1", "FRESH2")]
        assert set(gramps.media) == {"FRESH2"}
        row = conn.execute("SELECT source_id FROM minted_media WHERE gramps_id='XJ4DBT'").fetchone()
        assert row["source_id"] == "101"

    def test_register_conflict_is_a_failed_row_and_not_overwritten(self, conn):
        docs = [{"id": 1, "title": "New", "custom_fields": [], "tags": [1]}]
        events = self._sync(conn, self.Gramps(conn), docs)
        failed = [e for e in events if e.kind == "item" and e.action == "failed"]
        assert len(failed) == 1 and "immich a9" in failed[0].detail
        summary = next(e for e in events if e.kind == "summary")
        assert summary.data["created"] == 0 and summary.data["errors"] == 1
        row = conn.execute(
            "SELECT source_system, source_id FROM minted_media WHERE gramps_id=?",
            (failed[0].gramps_id,)).fetchone()
        assert tuple(row) == ("immich", "a9")


class TestTranscriptionOfNewDoc:

    class Paperless:
        def __init__(self, doc):
            self.doc = doc

        async def resolve_tag_id(self, name):
            return 1 if name == "doc" else None

        async def list_documents_by_tags(self, ids):
            return [copy.deepcopy(self.doc)]

        async def list_documents_by_tag(self, tag_id):  # a separate listing, like the real API
            return [copy.deepcopy(self.doc)]

        async def get_document_metadata(self, doc_id):
            return {"media_filename": f"{doc_id:07d}.jpg", "original_checksum": "c"}

        async def patch_custom_fields(self, doc_id, cfs):
            pass

    class Gramps:
        def __init__(self):
            self.media = {}
            self.notes = {}

        async def list_media_gramps_ids(self):
            return set(self.media)

        async def create_media(self, obj):
            self.media[obj["gramps_id"]] = obj

        async def get_media_by_gramps_id(self, gid):
            return self.media.get(gid)

        async def update_media(self, handle, obj):
            self.media[obj["gramps_id"]] = obj

        async def get_tag_handle(self, name):
            return None

        async def _paged(self, path, keys=None):
            return [{"gramps_id": n["gramps_id"]} for n in self.notes.values()]

        async def create_note(self, obj):
            self.notes[obj["handle"]] = obj

    def test_doc_created_this_run_gets_its_transcription_and_translation(self, tmp_path):
        doc = {"id": 1133, "title": "Death index", "custom_fields": [], "tags": [1, 43],
               "content": f"Siggerud\n{TRANSLATION_DELIMITER}\nSiggerud (en)"}
        cfg = SyncPaperlessConfig(sync_tags=("doc",), gramps_id_field_id=12,
                                  gramps_url_field_id=14, transcription_tag_id=43)
        conn = db.connect(tmp_path / "t.db")
        gramps = self.Gramps()

        async def collect():
            return [e async for e in sync_paperless.sync(
                self.Paperless(doc), gramps, conn, cfg, apply=True)]
        events = asyncio.run(collect())

        summary = next(e for e in events if e.kind == "summary")
        assert summary.data["created"] == 1 and summary.data["tx_created"] == 1
        (media,) = gramps.media.values()
        assert sorted(gramps.notes[h]["type"] for h in media["note_list"]) == [
            "Transcription", "Translation"]
        row = conn.execute(
            "SELECT gramps_media_id FROM transcription_state WHERE paperless_id=1133").fetchone()
        assert row["gramps_media_id"] == media["gramps_id"]
        conn.close()
