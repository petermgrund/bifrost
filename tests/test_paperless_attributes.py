"""Paperless custom fields mirrored as attributes on the Gramps media object"""

import asyncio
import copy

import pytest

from bifrost.core import db
from bifrost.core.clients.gramps import GrampsClient
from bifrost.core.config import ConfigError, SyncPaperlessConfig, load_config, parse_attribute_fields
from bifrost.modules import sync_paperless
from bifrost.modules.sync_paperless import attribute_changes, attribute_value, mirror_attributes

FIELDS = ((11, "Record URL"), (18, "Record URL access"), (21, "Date meaning"))
OPTIONS = {18: {"opt-pay": "Paywall", "opt-free": "Free"}, 21: {"opt-pub": "Publication"}}
CFG = SyncPaperlessConfig(sync_tags=("sync",), gramps_id_field_id=12, gramps_url_field_id=14,
                          attribute_fields=FIELDS)


def _attr(name, value):
    return {"_class": "Attribute", "type": name, "value": value,
            "private": False, "citation_list": [], "note_list": []}


def types_of(media):
    return [(a["type"], a["value"]) for a in media["attribute_list"]]


# ---- the pure helpers

class TestAttributeValue:

    def test_nothing_is_none(self):
        assert attribute_value(None) is None
        assert attribute_value("") is None
        assert attribute_value("   ") is None
        assert attribute_value([]) is None

    def test_text_is_stripped_and_numbers_become_text(self):
        assert attribute_value("  https://x/y ") == "https://x/y"
        assert attribute_value(42) == "42"

    def test_a_select_option_becomes_its_label(self):
        assert attribute_value("opt-pay", OPTIONS[18]) == "Paywall"
        assert attribute_value(3, {3: "Three"}) == "Three"

    def test_an_unknown_option_is_kept_as_written(self):
        assert attribute_value("opt-gone", OPTIONS[18]) == "opt-gone"

    def test_lists_join_and_booleans_read(self):
        assert attribute_value(["opt-pay", "opt-free"], OPTIONS[18]) == "Paywall, Free"
        assert attribute_value([7, 9]) == "7, 9"
        assert attribute_value(True) == "Yes" and attribute_value(False) == "No"


class TestMirrorAttributes:

    def media(self):
        return {"attribute_list": [_attr("Paperless URL", "http://p/documents/1/details"),
                                   _attr("Paperless ID", "1"),
                                   _attr("Record URL", "https://old"),
                                   _attr("Grund slideshow number", "4")]}

    def test_changes_are_named_and_nothing_else_moves(self):
        m = self.media()
        wanted = {"Record URL": "https://new", "Record URL access": "Paywall", "Date meaning": None}
        assert attribute_changes(m, wanted) == {"Record URL": "changed", "Record URL access": "new"}
        assert mirror_attributes(m, wanted) == {"Record URL": "changed", "Record URL access": "new"}
        assert types_of(m) == [("Paperless URL", "http://p/documents/1/details"), ("Paperless ID", "1"),
                               ("Record URL", "https://new"), ("Grund slideshow number", "4"),
                               ("Record URL access", "Paywall")]

    def test_in_sync_touches_nothing(self):
        m = self.media()
        before = copy.deepcopy(m)
        assert mirror_attributes(m, {"Record URL": "https://old", "Date meaning": None}) == {}
        assert m == before

    def test_an_empty_field_removes_the_attribute(self):
        m = self.media()
        assert mirror_attributes(m, {"Record URL": None}) == {"Record URL": "removed"}
        assert [t for t, _ in types_of(m)] == ["Paperless URL", "Paperless ID", "Grund slideshow number"]

    def test_duplicates_collapse_to_one(self):
        m = {"attribute_list": [_attr("Record URL", "https://a"), _attr("Record URL", "https://a")]}
        assert mirror_attributes(m, {"Record URL": "https://a"}) == {"Record URL": "changed"}
        assert types_of(m) == [("Record URL", "https://a")]

    def test_a_media_without_attributes(self):
        m = {}
        assert mirror_attributes(m, {"Provenance": "Carole Bixby"}) == {"Provenance": "new"}
        assert types_of(m) == [("Provenance", "Carole Bixby")]


# ---- the config

BASE = """\
gramps: {base_url: "http://g/api", username: u, password: p}
paperless: {base_url: "http://p", api_token: t}
"""


def _load(tmp_path, paperless_block):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(BASE + "sync:\n  paperless:\n" + paperless_block)
    return load_config(cfg)


class TestConfig:

    def test_absent_or_empty_is_off(self, tmp_path):
        assert _load(tmp_path, "    sync_tags: [sync]\n").sync_paperless.attribute_fields == ()
        assert _load(tmp_path, "    attribute_fields: {}\n").sync_paperless.attribute_fields == ()

    def test_a_mapping_in_order_with_numeric_or_quoted_ids(self, tmp_path):
        cfg = _load(tmp_path, '    attribute_fields:\n      11: "Record URL"\n      "18": Record URL access\n')
        assert cfg.sync_paperless.attribute_fields == ((11, "Record URL"), (18, "Record URL access"))

    @pytest.mark.parametrize("block", [
        '    attribute_fields: [11, 18]\n',
        '    attribute_fields:\n      eleven: "Record URL"\n',
        '    attribute_fields:\n      11: ""\n',
        '    attribute_fields:\n      11: "Record URL"\n      18: "Record URL"\n',
        '    attribute_fields:\n      11: "Paperless ID"\n',
        '    gramps_id_field_id: 12\n    attribute_fields:\n      12: "Gramps ID"\n',
    ])
    def test_refusals(self, tmp_path, block):
        with pytest.raises(ConfigError):
            _load(tmp_path, block)

    def test_parse_normalizes_whitespace(self):
        assert parse_attribute_fields({"attribute_fields": {"9": "  Record   URL "}}) == ((9, "Record URL"),)


# ---- the sync

class Paperless:
    def __init__(self, docs, broken=()):
        self.docs = docs
        self.broken = set(broken)
        self.option_calls = []

    async def resolve_tag_id(self, name):
        return 1 if name == "sync" else None

    async def list_documents_by_tags(self, ids):
        return self.docs

    async def get_document(self, doc_id):
        return next(d for d in self.docs if d["id"] == doc_id)

    async def get_document_metadata(self, doc_id):
        return {"media_filename": f"{doc_id:07d}.pdf", "original_checksum": "c"}

    async def patch_custom_fields(self, doc_id, cfs):
        pass

    async def resolve_custom_field_options(self, fid):
        self.option_calls.append(fid)
        if fid in self.broken:
            raise RuntimeError("404 no such field")
        return dict(OPTIONS.get(fid, {}))


class Gramps:
    def __init__(self):
        self.media = {}
        self.updates = 0

    async def list_media_gramps_ids(self):
        return set(self.media)

    async def create_media(self, obj):
        self.media[obj["gramps_id"]] = obj

    async def get_media_by_gramps_id(self, gid):
        # a fresh dict each time, like the API: a preview that mutated its copy would show here as no change
        found = self.media.get(gid)
        return copy.deepcopy(found) if found else None

    async def update_media(self, handle, obj):
        self.updates += 1
        self.media[obj["gramps_id"]] = obj

    async def media_md5(self, handle):
        return f"md5-{handle}"

    store_checksum = GrampsClient.store_checksum

    async def get_tag_handle(self, name):
        return None


def synced(gramps, fields, extra_attrs=()):
    gramps.media["DOC111"] = {
        "gramps_id": "DOC111", "handle": "h1", "desc": "Letter", "path": "paperless/0000001.pdf",
        "mime": "application/pdf", "checksum": "md5-h1",
        "attribute_list": [_attr("Paperless URL", "http://p/documents/1/details"), _attr("Paperless ID", "1"),
                           *extra_attrs]}
    return {"id": 1, "title": "Letter", "tags": [1],
            "custom_fields": [{"field": 12, "value": "DOC111"},
                              *({"field": f, "value": v} for f, v in fields)]}


FILLED = ((11, "https://example.org/record"), (18, "opt-pay"), (21, "opt-pub"))


def run(paperless, gramps, conn, apply, cfg=CFG, **kw):
    async def collect():
        return [e async for e in sync_paperless.sync(paperless, gramps, conn, cfg, apply=apply, **kw)]
    return asyncio.run(collect())


def media_events(events):
    return [e for e in events if e.kind == "item" and e.entity == "media"]


def summary(events):
    return next(e for e in events if e.kind == "summary").data


class TestSync:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "a.db")
        yield c
        c.close()

    def test_preview_names_the_attributes_and_writes_nothing(self, conn):
        gramps = Gramps()
        events = run(Paperless([synced(gramps, FILLED)]), gramps, conn, apply=False)
        (ev,) = media_events(events)
        assert ev.action == "would_update"
        assert ev.data["cols"] == {"Record URL": "new", "Record URL access": "new", "Date meaning": "new"}
        assert summary(events)["attributes_updated"] == 3
        assert gramps.updates == 0 and len(gramps.media["DOC111"]["attribute_list"]) == 2

    def test_apply_writes_them_after_the_keys_and_a_rerun_is_in_sync(self, conn):
        gramps = Gramps()
        paperless = Paperless([synced(gramps, FILLED)])
        events = run(paperless, gramps, conn, apply=True)
        (ev,) = media_events(events)
        assert ev.action == "updated"
        assert types_of(gramps.media["DOC111"]) == [
            ("Paperless URL", "http://p/documents/1/details"), ("Paperless ID", "1"),
            ("Record URL", "https://example.org/record"), ("Record URL access", "Paywall"),
            ("Date meaning", "Publication")]
        again = run(paperless, gramps, conn, apply=True)
        assert media_events(again) == [] and summary(again)["attributes_updated"] == 0
        assert gramps.updates == 1

    def test_a_changed_and_a_cleared_field_follow_in_place(self, conn):
        gramps = Gramps()
        doc = synced(gramps, FILLED)
        run(Paperless([doc]), gramps, conn, apply=True)
        doc["custom_fields"] = [{"field": 12, "value": "DOC111"}, {"field": 11, "value": "https://example.org/v2"},
                                {"field": 18, "value": ""}, {"field": 21, "value": "opt-pub"}]
        events = run(Paperless([doc]), gramps, conn, apply=True)
        (ev,) = media_events(events)
        assert ev.data["cols"] == {"Record URL": "changed", "Record URL access": "removed"}
        assert types_of(gramps.media["DOC111"]) == [
            ("Paperless URL", "http://p/documents/1/details"), ("Paperless ID", "1"),
            ("Record URL", "https://example.org/v2"), ("Date meaning", "Publication")]

    def test_an_edit_made_in_gramps_is_overwritten(self, conn):
        gramps = Gramps()
        doc = synced(gramps, FILLED, extra_attrs=[_attr("Record URL", "https://typed-in-gramps")])
        events = run(Paperless([doc]), gramps, conn, apply=True)
        (ev,) = media_events(events)
        assert ev.data["cols"]["Record URL"] == "changed"
        assert ("Record URL", "https://example.org/record") in types_of(gramps.media["DOC111"])

    def test_a_field_paperless_cannot_describe_is_left_alone_this_run(self, conn):
        gramps = Gramps()
        doc = synced(gramps, FILLED, extra_attrs=[_attr("Record URL access", "Free")])
        paperless = Paperless([doc], broken={18})
        events = run(paperless, gramps, conn, apply=True)
        errors = [e for e in events if e.kind == "error"]
        assert len(errors) == 1 and "attribute field 18 (Record URL access)" in errors[0].detail
        (ev,) = media_events(events)
        assert ev.data["cols"] == {"Record URL": "new", "Date meaning": "new"}
        assert ("Record URL access", "Free") in types_of(gramps.media["DOC111"])

    def test_a_document_created_this_run_gets_its_attributes(self, conn):
        gramps = Gramps()
        doc = {"id": 3, "title": "New", "tags": [1],
               "custom_fields": [{"field": f, "value": v} for f, v in FILLED]}
        events = run(Paperless([doc]), gramps, conn, apply=True)
        created = next(e for e in events if e.action == "created")
        assert created.data["cols"] == {"Record URL": "new", "Record URL access": "new", "Date meaning": "new"}
        (media,) = gramps.media.values()
        assert [t for t, _ in types_of(media)] == [
            "Paperless URL", "Paperless ID", "Record URL", "Record URL access", "Date meaning"]
        preview = run(Paperless([doc]), gramps, conn, apply=False)
        assert media_events(preview) == []

    def test_version_and_transcription_runs_do_not_look_at_fields(self, conn):
        gramps = Gramps()
        paperless = Paperless([synced(gramps, FILLED)])
        for kw in ({"versions_only": True}, {"transcriptions_only": True}):
            events = run(paperless, gramps, conn, apply=True, **kw)
            assert media_events(events) == []
        assert paperless.option_calls == [] and gramps.updates == 0

    def test_a_single_document_run_mirrors_it(self, conn):
        gramps = Gramps()
        other = {"id": 2, "title": "Other", "tags": [1],
                 "custom_fields": [{"field": 12, "value": "OTHER2"}, {"field": 11, "value": "https://other"}]}
        gramps.media["OTHER2"] = {"gramps_id": "OTHER2", "handle": "h2", "desc": "Other",
                                  "path": "paperless/0000002.pdf", "mime": "application/pdf",
                                  "checksum": "md5-h2", "attribute_list": [_attr("Paperless ID", "2")]}
        paperless = Paperless([synced(gramps, FILLED), other])
        events = run(paperless, gramps, conn, apply=True, single_doc_id=1)
        assert [e.source_id for e in media_events(events)] == ["1"]
        assert ("Record URL", "https://example.org/record") in types_of(gramps.media["DOC111"])
        assert types_of(gramps.media["OTHER2"]) == [("Paperless ID", "2")]

    def test_off_without_configured_fields(self, conn):
        gramps = Gramps()
        paperless = Paperless([synced(gramps, FILLED)])
        plain = SyncPaperlessConfig(sync_tags=("sync",), gramps_id_field_id=12, gramps_url_field_id=14)
        events = run(paperless, gramps, conn, apply=True, cfg=plain)
        assert media_events(events) == [] and paperless.option_calls == []
        assert "attributes_updated" in summary(events)
