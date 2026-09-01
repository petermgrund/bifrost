import asyncio

import pytest

from bifrost.core import db
from bifrost.core.clients.immich import ImmichError
from bifrost.core.config import SyncImmichConfig
from bifrost.modules import sync_immich
from bifrost.modules.sync_immich import SyncError, person_links_map, translate_path

MAPPINGS = (
    ("/usr/src/app/upload/upload/", "immich/"),
    ("/mnt/archive/", "archive/"),
)


class TestTranslatePath:
    def test_managed_library(self):
        assert (
            translate_path("/usr/src/app/upload/upload/u1/ab/cd/x.jpg", MAPPINGS)
            == "immich/u1/ab/cd/x.jpg"
        )

    def test_external_library(self):
        assert translate_path("/mnt/archive/shoebox/y.jpg", MAPPINGS) == "archive/shoebox/y.jpg"

    def test_first_match_wins(self):
        doubled = (("/mnt/", "wrong/"), ("/mnt/archive/", "archive/"))
        assert translate_path("/mnt/archive/z.jpg", doubled) == "wrong/archive/z.jpg"

    def test_no_mapping_is_hard_error(self):
        with pytest.raises(SyncError) as exc:
            translate_path("/somewhere/else/x.jpg", MAPPINGS)
        assert exc.value.status == 400


class TestDateCodePins:
    def test_modifier_codes(self):
        assert sync_immich._MODIFIERS == {
            "regular": 0, "before": 1, "after": 2, "about": 3,
            "range": 4, "span": 5, "textonly": 6,
        }

    def test_quality_codes(self):
        assert sync_immich._QUALITIES == {"regular": 0, "estimated": 1, "calculated": 2}


class TestMergeTagValues:
    def test_plain_union(self):
        assert sync_immich.merge_tag_values(
            {"sync/gramps", "sync/date"}, {"sync/description"},
        ) == {"sync/gramps", "sync/date", "sync/description"}

    def test_owner_wins_modifier_group(self):
        got = sync_immich.merge_tag_values(
            {"date/before"}, {"date/after", "sync/location"})
        assert got == {"date/before", "sync/location"}

    def test_owner_wins_precision_group(self):
        got = sync_immich.merge_tag_values({"date/year"}, {"date/month"})
        assert got == {"date/year"}

    def test_other_fills_group_owner_lacks(self):
        got = sync_immich.merge_tag_values(
            {"date/approximate"}, {"date/estimated", "date/month"})
        assert got == {"date/approximate", "date/estimated", "date/month"}

    def test_empty_owner_keeps_other(self):
        assert sync_immich.merge_tag_values(set(), {"date/before"}) == {"date/before"}


class FakeImmich:
    """Duck-typed ImmichClient for scan"""

    def __init__(self, *, assets=None, stacks=None, tagged=(), tag_name="Sync/Gramps",
                 fail_detail=(), page_size=None, me_id="me-1", faces=None):
        self.tag = {"id": "tag-1", "name": tag_name, "value": tag_name}
        self.assets = assets or {}
        self.stacks = stacks or []
        self.tagged = set(tagged)
        self.fail_detail = set(fail_detail)
        self.page_size = page_size
        self.me_id = me_id
        self.label = me_id
        self.faces = faces or {}
        self.faces_requested = []
        self.search_calls = 0
        self.list_stacks_calls = 0
        self.get_me_calls = 0
        self.extra_tags = {}          # value.lower() -> tag dict
        self.upserted = []
        self.tagged_assets = []
        self.untagged_assets = []
        self.fail_tag_write = False

    async def get_me(self):
        self.get_me_calls += 1
        return {"id": self.me_id}

    async def find_tag(self, name):
        if name.lower() == self.tag["value"].lower():
            return self.tag
        return self.extra_tags.get(name.lower())

    async def upsert_tag(self, path):
        if self.fail_tag_write:
            raise ImmichError(500, "tag write boom")
        self.upserted.append(path)
        tag = self.extra_tags.get(path.lower())
        if tag is None:
            tag = {"id": f"tag-{len(self.extra_tags) + 2}",
                   "name": path.split("/")[-1], "value": path}
            self.extra_tags[path.lower()] = tag
        return tag

    async def tag_asset(self, tag_id, asset_id):
        if self.fail_tag_write:
            raise ImmichError(500, "tag write boom")
        self.tagged_assets.append((tag_id, asset_id))

    async def untag_asset(self, tag_id, asset_id):
        self.untagged_assets.append((tag_id, asset_id))

    async def list_stacks(self):
        self.list_stacks_calls += 1
        return self.stacks

    async def search_assets(self, page=1, size=60, person_id=None,
                            filename=None, order="desc", tag_id=None):
        assert tag_id == self.tag["id"], "the scan must search by the trigger tag"
        self.search_calls += 1
        size = min(size, self.page_size or size)
        items = [self.assets[i] for i in sorted(self.tagged)]
        start = (page - 1) * size
        return {"items": items[start:start + size],
                "nextPage": page + 1 if start + size < len(items) else None}

    async def get_asset(self, asset_id):
        if asset_id not in self.assets:
            raise ImmichError(404, "asset not found")
        return self.assets[asset_id]

    async def get_assets_many(self, asset_ids, concurrency=8):
        return {i: (None if i in self.fail_detail else self.assets.get(i))
                for i in asset_ids}

    async def get_faces(self, asset_id):
        self.faces_requested.append(asset_id)
        return self.faces.get(asset_id, [])


class FakeGramps:
    def __init__(self, media=None, places=None, people=None):
        self.media = media or {}
        self.created = []
        self.updated = []
        self.places = places or []
        self.updated_places = []
        self.people = people or {}
        self.updated_people = []

    async def get_media_by_gramps_id(self, gid):
        return self.media.get(gid)

    async def list_media_gramps_ids(self):
        return set(self.media)

    async def create_media(self, obj):
        self.media[obj["gramps_id"]] = obj
        self.created.append(obj)

    async def update_media(self, handle, obj):
        self.updated.append(obj)

    async def list_places_full(self):
        return self.places

    async def update_place(self, handle, place_obj):
        self.updated_places.append(place_obj)

    async def get_person(self, handle):
        return self.people[handle]

    async def update_person(self, handle, person_obj):
        self.updated_people.append(person_obj)


CFG = SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="")
ID_CFG = SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="ID")


def asset(aid, name="img.jpg", path=None):
    return {"id": aid, "originalFileName": name,
            "originalPath": path or f"/up/{name}", "originalMimeType": "image/jpeg"}


def run_scan(immich, gramps, conn, apply=False, selected=None, cfg=CFG, partner=None):
    accounts = [immich] + ([partner] if partner is not None else [])
    async def collect():
        return [e async for e in sync_immich.sync_assets(
            gramps, accounts, conn, cfg, apply=apply, selected=selected)]
    return asyncio.run(collect())


def actions(events, action):
    return [e for e in events if e.kind == "item" and e.action == action]


def summary_of(events):
    return [e for e in events if e.kind == "summary"][-1]


class TestSyncAssetsScan:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        c.execute(
            "INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
            "VALUES ('h-ed', 'uuid-ed', 'Ed', 't')")
        yield c
        c.close()

    def _mint(self, conn, gid, source_id, title="t"):
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES (?, 'immich', ?, ?, '2026-01-01')", (gid, source_id, title))
        conn.commit()

    def test_progress_covers_every_band_and_closes_each(self, conn):
        self._mint(conn, "K1", "a2")
        im = FakeImmich(assets={"a1": asset("a1"), "a2": asset("a2")}, tagged={"a1"})
        gr = FakeGramps(media={"K1": {"gramps_id": "K1", "handle": "mh", "desc": "t",
                                      "path": "immich/img.jpg", "mime": "image/jpeg"}})
        events = run_scan(im, gr, conn)
        progress = [e.data for e in events if e.kind == "progress"]
        assert progress and {d["band_count"] for d in progress} == {3}
        assert [d["band_index"] for d in progress] == sorted(d["band_index"] for d in progress)
        for band in range(3):
            steps = [d for d in progress if d["band_index"] == band]
            assert steps, f"band {band} never reported"
            assert steps[-1]["done"] == steps[-1]["total"] > 0
        assert events.index(next(e for e in events if e.kind == "summary")) > \
            events.index(next(e for e in reversed(events) if e.kind == "progress"))

    def test_tagged_unsynced_is_a_create_candidate(self, conn):
        im = FakeImmich(assets={"a1": asset("a1", "img1.jpg")}, tagged={"a1"})
        events = run_scan(im, FakeGramps(), conn)
        creates = actions(events, "would_create")
        assert [e.source_id for e in creates] == ["a1"]
        assert creates[0].title == "img1.jpg"

    def test_untagged_is_not_a_candidate(self, conn):
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Description"}]
        a["exifInfo"] = {"description": "Grandma"}
        im = FakeImmich(assets={"a1": a}, tagged=set())
        events = run_scan(im, FakeGramps(), conn)
        assert actions(events, "would_create") == []
        assert actions(events, "would_update") == []

    def test_tagged_variant_with_governed_main_skipped_silently(self, conn):
        stacks = [{"id": "s1", "primaryAssetId": "p1",
                   "assets": [{"id": "p1"}, {"id": "c1"}]}]
        im = FakeImmich(assets={"p1": asset("p1"), "c1": asset("c1")},
                        stacks=stacks, tagged={"p1", "c1"})
        events = run_scan(im, FakeGramps(), conn)
        assert [e.source_id for e in actions(events, "would_create")] == ["p1"]
        assert actions(events, "failed") == []

    def test_tagged_orphan_variant_is_surfaced(self, conn):
        stacks = [{"id": "s1", "primaryAssetId": "p1",
                   "assets": [{"id": "p1"}, {"id": "c1"}]}]
        im = FakeImmich(assets={"p1": asset("p1"), "c1": asset("c1")},
                        stacks=stacks, tagged={"c1"})
        events = run_scan(im, FakeGramps(), conn)
        failed = actions(events, "failed")
        assert len(failed) == 1 and "variant" in failed[0].detail

    def test_synced_media_updates_without_the_tag(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1", "img.jpg")
        a["tags"] = [{"value": "Sync/Description"}]
        a["exifInfo"] = {"description": "New title"}
        im = FakeImmich(assets={"a1": a}, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "Old title", "path": "immich/img.jpg",
                                    "attribute_list": [
                                        {"type": "Immich ID", "value": "a1"}]}})
        events = run_scan(im, gr, conn)
        updates = actions(events, "would_update")
        assert len(updates) == 1 and set(updates[0].data["cols"]) == {"title"}

    def test_stale_immich_attrs_heal_without_a_file_move(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1", "img.jpg")}, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "t", "path": "immich/img.jpg",
                                    "attribute_list": [
                                        {"type": "Immich ID", "value": "gone1"},
                                        {"type": "Immich URL",
                                         "value": "https://img/photos/gone1"}]}})
        cfg = SyncImmichConfig(path_mappings=(("/up/", "immich/"),),
                               public_url="https://img", id_tag_prefix="")
        preview = run_scan(im, gr, conn, cfg=cfg)
        updates = actions(preview, "would_update")
        assert len(updates) == 1 and set(updates[0].data["cols"]) == {"link"}
        events = run_scan(im, gr, conn, apply=True, cfg=cfg)
        media = gr.updated[0]
        assert media["path"] == "immich/img.jpg"
        attrs = {a["type"]: a["value"] for a in media["attribute_list"]}
        assert attrs["Immich ID"] == "a1"
        assert attrs["Immich URL"].endswith("/photos/a1")
        assert summary_of(events).data["links_updated"] == 1

    def test_missing_attr_list_gets_linked(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1", "img.jpg")}, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "t", "path": "immich/img.jpg"}})
        run_scan(im, gr, conn, apply=True)
        attrs = {a["type"]: a["value"] for a in gr.updated[0]["attribute_list"]}
        assert attrs["Immich ID"] == "a1"

    def test_tagged_synced_in_step_asset_just_skips(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1", "img.jpg")}, tagged={"a1"})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "t", "path": "immich/img.jpg",
                                    "attribute_list": [
                                        {"type": "Immich ID", "value": "a1"}]}})
        events = run_scan(im, gr, conn, apply=True)
        assert gr.created == [] and gr.updated == []
        assert summary_of(events).data["skipped"] == 1

    def test_moved_main_measured_against_current_primary(self, conn):
        self._mint(conn, "BBBBBB", "old1")
        stacks = [{"id": "s1", "primaryAssetId": "new1",
                   "assets": [{"id": "new1"}, {"id": "old1"}]}]
        im = FakeImmich(
            assets={"new1": asset("new1", "new.jpg"), "old1": asset("old1", "old.jpg")},
            stacks=stacks, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "T", "path": "immich/old.jpg",
                                    "attribute_list": []}})
        events = run_scan(im, gr, conn)
        updates = actions(events, "would_update")
        assert len(updates) == 1
        assert updates[0].source_id == "new1"
        assert set(updates[0].data["cols"]) == {"file", "link"}
        assert "new.jpg" in updates[0].data["cols"]["file"]

    def test_apply_repoints_file_and_register(self, conn):
        self._mint(conn, "BBBBBB", "old1")
        stacks = [{"id": "s1", "primaryAssetId": "new1",
                   "assets": [{"id": "new1"}, {"id": "old1"}]}]
        im = FakeImmich(
            assets={"new1": asset("new1", "new.jpg"), "old1": asset("old1", "old.jpg")},
            stacks=stacks, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "T", "path": "immich/old.jpg",
                                    "attribute_list": []}})
        events = run_scan(im, gr, conn, apply=True)
        assert len(gr.updated) == 1
        media = gr.updated[0]
        assert media["path"] == "immich/new.jpg"
        assert media["desc"] == "T"
        attrs = {a["type"]: a["value"] for a in media["attribute_list"]}
        assert attrs["Immich ID"] == "new1"
        row = conn.execute(
            "SELECT source_id FROM minted_media WHERE gramps_id='BBBBBB'").fetchone()
        assert row["source_id"] == "new1"
        assert summary_of(events).data["versions_updated"] == 1

    def test_apply_writes_title_and_date_drift(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Description"}, {"value": "Sync/Date"}]
        a["exifInfo"] = {"description": "New title",
                         "dateTimeOriginal": "1955-07-14T10:00:00Z"}
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "Old title", "path": "immich/img.jpg",
                                    "date": None}})
        events = run_scan(im, gr, conn, apply=True)
        assert len(gr.updated) == 1
        media = gr.updated[0]
        assert media["desc"] == "New title"
        assert sync_immich.dates_equal(media["date"], sync_immich.build_gramps_date(a))
        s = summary_of(events).data
        assert s["titles_updated"] == 1 and s["dates_updated"] == 1

    def test_moved_main_with_tagged_metadata_updates_file_title_date(self, conn):
        self._mint(conn, "BBBBBB", "old1")
        stacks = [{"id": "s1", "primaryAssetId": "new1",
                   "assets": [{"id": "new1"}, {"id": "old1"}]}]
        new1 = asset("new1", "new.jpg")
        new1["tags"] = [{"value": "Sync/Description"}, {"value": "Sync/Date"}]
        new1["exifInfo"] = {"description": "Curated title",
                            "dateTimeOriginal": "1920-06-01T10:00:00Z"}
        im = FakeImmich(assets={"new1": new1, "old1": asset("old1", "old.jpg")},
                        stacks=stacks, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "T", "path": "immich/old.jpg",
                                    "date": None, "attribute_list": []}})
        preview = run_scan(im, gr, conn)
        updates = actions(preview, "would_update")
        assert len(updates) == 1
        assert set(updates[0].data["cols"]) == {"file", "title", "date", "link"}
        run_scan(im, gr, conn, apply=True)
        media = gr.updated[0]
        assert media["path"] == "immich/new.jpg"
        assert media["desc"] == "Curated title"
        assert sync_immich.dates_equal(media["date"], sync_immich.build_gramps_date(new1))
        attrs = {a["type"]: a["value"] for a in media["attribute_list"]}
        assert attrs["Immich ID"] == "new1"

    def test_tag_sweep_collects_all_pages(self):
        im = FakeImmich(assets={f"a{i}": asset(f"a{i}") for i in range(5)},
                        tagged={f"a{i}" for i in range(5)}, page_size=2)
        items, capped = asyncio.run(sync_immich._tagged_scope(im, "tag-1"))
        assert sorted(a["id"] for a in items) == [f"a{i}" for i in range(5)]
        assert not capped
        assert im.search_calls == 3

    def test_tag_sweep_cap_warns_and_proceeds(self, conn, monkeypatch):
        monkeypatch.setattr(sync_immich, "_TAG_ASSET_CAP", 2)
        im = FakeImmich(assets={f"a{i}": asset(f"a{i}") for i in range(3)},
                        tagged={f"a{i}" for i in range(3)}, page_size=1)
        events = run_scan(im, FakeGramps(), conn)
        started = [e for e in events if e.kind == "started"][0]
        assert "CAPPED" in started.detail
        assert len(actions(events, "would_create")) == 2

    def test_tagged_primary_of_registered_variant_is_a_repoint_not_a_create(self, conn):
        self._mint(conn, "BBBBBB", "old1")
        stacks = [{"id": "s1", "primaryAssetId": "new1",
                   "assets": [{"id": "new1"}, {"id": "old1"}]}]
        im = FakeImmich(
            assets={"new1": asset("new1", "new.jpg"), "old1": asset("old1", "old.jpg")},
            stacks=stacks, tagged={"new1"})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "T", "path": "immich/old.jpg",
                                    "attribute_list": []}})
        events = run_scan(im, gr, conn, apply=True)
        assert actions(events, "would_create") == []
        assert gr.created == []
        assert len(gr.updated) == 1 and gr.updated[0]["path"] == "immich/new.jpg"
        assert gr.updated[0]["desc"] == "T"

    def test_registered_asset_gone_from_immich_is_surfaced(self, conn):
        self._mint(conn, "BBBBBB", "gone1")
        im = FakeImmich(assets={}, tagged=set())
        events = run_scan(im, FakeGramps(), conn)
        failed = actions(events, "failed")
        assert len(failed) == 1 and failed[0].gramps_id == "BBBBBB"

    def test_trashed_registered_asset_is_surfaced(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["isTrashed"] = True
        im = FakeImmich(assets={"a1": a}, tagged=set())
        events = run_scan(im, FakeGramps(), conn)
        failed = actions(events, "failed")
        assert len(failed) == 1 and "trash" in failed[0].detail

    def test_register_pointing_at_missing_gramps_media_is_surfaced(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1")}, tagged=set())
        events = run_scan(im, FakeGramps(), conn)
        failed = actions(events, "failed")
        assert len(failed) == 1 and "not in Gramps" in failed[0].detail

    def test_two_media_resolving_to_one_main_both_error(self, conn):
        self._mint(conn, "G1G1G1", "o1")
        self._mint(conn, "G2G2G2", "o2")
        stacks = [{"id": "s1", "primaryAssetId": "o1",
                   "assets": [{"id": "o1"}, {"id": "o2"}]}]
        im = FakeImmich(assets={"o1": asset("o1"), "o2": asset("o2")}, stacks=stacks)
        events = run_scan(im, FakeGramps(), conn)
        failed = actions(events, "failed")
        assert len(failed) == 2
        assert all("same stack main" in f.detail for f in failed)
        assert actions(events, "would_update") == []

    def test_unmapped_path_errors_without_aborting_the_batch(self, conn):
        self._mint(conn, "G1G1G1", "a1")
        self._mint(conn, "G2G2G2", "a2")
        a1 = asset("a1", path="/somewhere/else/x.jpg")
        a2 = asset("a2", "b.jpg")
        a2["tags"] = [{"value": "Sync/Description"}]
        a2["exifInfo"] = {"description": "Drifted"}
        im = FakeImmich(assets={"a1": a1, "a2": a2}, tagged=set())
        gr = FakeGramps({
            "G1G1G1": {"gramps_id": "G1G1G1", "handle": "h1", "desc": "t", "path": "x"},
            "G2G2G2": {"gramps_id": "G2G2G2", "handle": "h2", "desc": "t", "path": "immich/b.jpg"},
        })
        events = run_scan(im, gr, conn)
        failed = actions(events, "failed")
        assert len(failed) == 1 and "path mapping" in failed[0].detail
        assert len(actions(events, "would_update")) == 1

    def test_detail_fetch_failure_is_surfaced(self, conn):
        im = FakeImmich(assets={"a1": asset("a1")}, tagged={"a1"}, fail_detail={"a1"})
        events = run_scan(im, FakeGramps(), conn)
        failed = actions(events, "failed")
        assert len(failed) == 1 and "detail fetch failed" in failed[0].detail
        assert summary_of(events).data["errors"] == 1

    def test_missing_trigger_tag_aborts(self, conn):
        im = FakeImmich(tag_name="Something/Else")
        with pytest.raises(SyncError) as exc:
            run_scan(im, FakeGramps(), conn)
        assert exc.value.status == 400

    def test_stacks_listing_failure_aborts(self, conn):
        class NoStacksImmich(FakeImmich):
            async def list_stacks(self):
                raise ImmichError(500, "boom")

        with pytest.raises(SyncError) as exc:
            run_scan(NoStacksImmich(), FakeGramps(), conn)
        assert exc.value.status == 502

    def test_places_listing_failure_skips_links_not_the_scan(self, conn):
        class NoPlacesGramps(FakeGramps):
            async def list_places_full(self):
                raise RuntimeError("gramps down")

        im = FakeImmich(assets={"a1": asset("a1")}, tagged={"a1"})
        events = run_scan(im, NoPlacesGramps(), conn, cfg=PLACE_CFG)
        failed = actions(events, "failed")
        assert len(failed) == 1 and "place links skipped" in failed[0].detail
        assert len(actions(events, "would_create")) == 1

    def test_apply_create_mints_and_registers(self, conn):
        im = FakeImmich(assets={"a1": asset("a1", "img1.jpg")}, tagged={"a1"})
        gr = FakeGramps()
        events = run_scan(im, gr, conn, apply=True)
        assert len(gr.created) == 1
        gid = gr.created[0]["gramps_id"]
        row = conn.execute(
            "SELECT gramps_id FROM minted_media WHERE source_system='immich' AND source_id='a1'"
        ).fetchone()
        assert row and row["gramps_id"] == gid
        assert summary_of(events).data["created"] == 1


def test_sync_counts_are_all_initialized():
    import inspect
    import re

    src = inspect.getsource(sync_immich.sync_assets)
    init = re.search(r"counts\s*=\s*\{(.*?)\}", src, re.S).group(1)
    declared = set(re.findall(r"\"(\w+)\"\s*:", init))
    used = set(re.findall(r"counts\[\"(\w+)\"\]", src))
    assert used <= declared, f"uninitialized counts keys: {used - declared}"


class TestSyncOneAsset:
    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        c.execute(
            "INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
            "VALUES ('h-ed', 'uuid-ed', 'Ed', 't')")
        yield c
        c.close()

    def _run(self, im, gr, conn, asset_id, gramps_id=None):
        async def collect():
            return [e async for e in sync_immich.sync_one_asset(
                gr, [im], conn, CFG, asset_id, gramps_id=gramps_id)]
        return asyncio.run(collect())

    def test_create_uses_tag_metadata(self, conn):
        a = asset("a1", "img.jpg")
        a["tags"] = [{"value": "Sync/Description"}, {"value": "Sync/Date"},
                     {"value": "date/approximate"}]
        a["exifInfo"] = {"description": "Easter 1966"}
        a["localDateTime"] = "1966-04-10T09:00:00Z"
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps()
        events = self._run(im, gr, conn, "a1")
        summary = summary_of(events)
        assert summary.data["created"] is True
        assert summary.data["title"] == "Easter 1966"
        assert "warning" not in summary.data
        assert gr.created[0]["date"]["dateval"] == [0, 4, 1966, False]
        row = conn.execute(
            "SELECT gramps_id FROM minted_media WHERE source_id='a1'").fetchone()
        assert row["gramps_id"] == summary.data["gramps_id"]

    def test_rerun_resumes_via_register_only(self, conn):
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES ('BBBBBB', 'immich', 'a1', 'T', '2026-01-01')")
        conn.commit()
        im = FakeImmich(assets={"a1": asset("a1")})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "T", "path": "immich/img.jpg"}})
        events = self._run(im, gr, conn, "a1")
        assert gr.created == []
        assert summary_of(events).data["created"] is False
        assert len(actions(events, "skipped")) == 1

    def test_primary_of_registered_variant_resumes_not_mints(self, conn):
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES ('BBBBBB', 'immich', 'c1', 'T', '2026-01-01')")
        conn.commit()
        p = asset("p1", "new.jpg")
        p["stack"] = {"primaryAssetId": "p1"}
        im = FakeImmich(assets={"p1": p, "c1": asset("c1", "old.jpg")},
                        stacks=[{"id": "s1", "primaryAssetId": "p1",
                                 "assets": [{"id": "p1"}, {"id": "c1"}]}])
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "T", "path": "immich/old.jpg"}})
        events = self._run(im, gr, conn, "p1")
        assert gr.created == []
        assert summary_of(events).data["created"] is False
        assert len(actions(events, "skipped")) == 1
        rows = conn.execute("SELECT source_id FROM minted_media").fetchall()
        assert [r["source_id"] for r in rows] == ["c1"]

    def test_two_register_rows_through_the_stack_error(self, conn):
        conn.executemany(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES (?, 'immich', ?, 'T', '2026-01-01')",
            [("G1G1G1", "c1"), ("G2G2G2", "c2")])
        conn.commit()
        p = asset("p1")
        p["stack"] = {"primaryAssetId": "p1"}
        im = FakeImmich(assets={"p1": p},
                        stacks=[{"id": "s1", "primaryAssetId": "p1",
                                 "assets": [{"id": "p1"}, {"id": "c1"}, {"id": "c2"}]}])
        with pytest.raises(SyncError) as exc:
            self._run(im, FakeGramps(), conn, "p1")
        assert exc.value.status == 400 and "same stack main" in exc.value.detail

    def test_unstacked_create_skips_stack_listing(self, conn):
        im = FakeImmich(assets={"a1": asset("a1")})
        self._run(im, FakeGramps(), conn, "a1")
        assert im.list_stacks_calls == 0

    def test_trashed_asset_refused(self, conn):
        a = asset("a1")
        a["isTrashed"] = True
        with pytest.raises(SyncError) as exc:
            self._run(FakeImmich(assets={"a1": a}), FakeGramps(), conn, "a1")
        assert exc.value.status == 400 and "trash" in exc.value.detail

    def test_stack_variant_refused(self, conn):
        a = asset("a1")
        a["stack"] = {"primaryAssetId": "other"}
        with pytest.raises(SyncError) as exc:
            self._run(FakeImmich(assets={"a1": a}), FakeGramps(), conn, "a1")
        assert exc.value.status == 400 and "variant" in exc.value.detail

    def test_missing_asset_404(self, conn):
        with pytest.raises(SyncError) as exc:
            self._run(FakeImmich(), FakeGramps(), conn, "nope")
        assert exc.value.status == 404

    def test_manual_gramps_id(self, conn):
        im = FakeImmich(assets={"a1": asset("a1"), "a2": asset("a2")})
        gr = FakeGramps()
        events = self._run(im, gr, conn, "a1", gramps_id="abcdef")
        assert summary_of(events).data["gramps_id"] == "ABCDEF"
        with pytest.raises(SyncError) as exc:
            self._run(im, gr, conn, "a2", gramps_id="bad id")
        assert exc.value.status == 400 and "invalid" in exc.value.detail


class TestTagDate:
    """build_gramps_date"""

    def _asset(self, *tags, dt="1955-07-14T10:00:00Z"):
        return {"exifInfo": {"dateTimeOriginal": dt},
                "tags": [{"value": t} for t in tags]}

    def test_plain_exif_date(self):
        d = sync_immich.build_gramps_date(self._asset())
        assert d["dateval"] == [14, 7, 1955, False]
        assert d["modifier"] == 0 and d["quality"] == 0

    def test_approximate_strips_the_day(self):
        d = sync_immich.build_gramps_date(self._asset("date/approximate"))
        assert d["dateval"] == [0, 7, 1955, False]
        assert d["modifier"] == 3

    def test_precision_modifier_quality_compose(self):
        d = sync_immich.build_gramps_date(
            self._asset("date/year", "date/estimated", "date/before"))
        assert d["dateval"] == [0, 0, 1955, False]
        assert d["modifier"] == 1 and d["quality"] == 1

    def test_month_precision(self):
        d = sync_immich.build_gramps_date(self._asset("date/month", "date/calculated"))
        assert d["dateval"] == [0, 7, 1955, False]
        assert d["quality"] == 2

    def test_no_exif_no_date(self):
        assert sync_immich.build_gramps_date({"tags": [{"value": "date/year"}]}) is None

    def test_wall_clock_wins_over_utc_instant(self):
        a = {"localDateTime": "1966-04-10T21:30:00.000Z",
             "exifInfo": {"dateTimeOriginal": "1966-04-11T02:30:00.000Z"},
             "tags": []}
        assert sync_immich.build_gramps_date(a)["dateval"] == [10, 4, 1966, False]

    def test_garbage_exif_no_date(self):
        assert sync_immich.build_gramps_date(self._asset(dt="not a date")) is None


class TestTagTitleAndDate:
    def test_description_needs_the_gate(self):
        a = {"originalFileName": "f.jpg", "exifInfo": {"description": "Desc"}, "tags": []}
        assert sync_immich.wanted_title(a) == "f.jpg"
        a["tags"] = [{"value": "Sync/Description"}]
        assert sync_immich.wanted_title(a) == "Desc"

    def test_empty_description_falls_back(self):
        a = {"originalFileName": "f.jpg", "exifInfo": {"description": "  "},
             "tags": [{"value": "Sync/Description"}]}
        assert sync_immich.wanted_title(a) == "f.jpg"
        assert sync_immich.wanted_update_title(a) is None

    def test_filename_never_drives_an_update(self):
        a = {"originalFileName": "f.jpg", "tags": []}
        assert sync_immich.wanted_update_title(a) is None

    def test_exif_date_needs_the_gate(self):
        a = {"exifInfo": {"dateTimeOriginal": "1955-07-14T10:00:00Z"}, "tags": []}
        assert sync_immich.wanted_date(a) == (None, "")
        a["tags"] = [{"value": "Sync/Date"}]
        d, display = sync_immich.wanted_date(a)
        assert d["dateval"] == [14, 7, 1955, False]
        assert display


class TestUpdatePlan:
    MAPPED = SyncImmichConfig(path_mappings=(("/usr/src/app/upload/upload/", "immich/"),))

    def test_dates_equal_ignores_api_decoration(self):
        stored = {"_class": "Date", "dateval": [0, 7, 1955, False], "modifier": 3,
                  "quality": 0, "text": "", "sortval": 2422325, "calendar": 0}
        fresh = sync_immich.build_gramps_date(
            {"exifInfo": {"dateTimeOriginal": "1955-07-14T10:00:00Z"},
             "tags": [{"value": "date/approximate"}]})
        assert sync_immich.dates_equal(stored, fresh)

    def test_dates_differ(self):
        assert not sync_immich.dates_equal(
            {"dateval": [0, 0, 1920, False], "modifier": 3, "quality": 1},
            {"dateval": [0, 0, 1921, False], "modifier": 3, "quality": 1})
        assert not sync_immich.dates_equal(None, {"dateval": [0, 0, 1920, False]})

    def test_title_and_date_drift(self):
        a = {"originalFileName": "img_0001.jpg",
             "exifInfo": {"description": "Grandma, 1920",
                          "dateTimeOriginal": "1920-06-01T10:00:00Z"},
             "tags": [{"value": "Sync/Description"}, {"value": "Sync/Date"}]}
        media = {"desc": "img_0001.jpg", "date": None}
        assert set(sync_immich.update_plan(a, media, self.MAPPED)) == {"title", "date"}

    def test_in_sync(self):
        a = {"exifInfo": {"description": "T",
                          "dateTimeOriginal": "1955-07-14T10:00:00Z"},
             "tags": [{"value": "Sync/Description"}, {"value": "Sync/Date"}]}
        media = {"desc": "T", "date": {"dateval": [14, 7, 1955, False],
                                       "modifier": 0, "quality": 0, "text": ""}}
        assert sync_immich.update_plan(a, media, self.MAPPED) == {}

    def test_never_clears_gramps_date(self):
        media = {"desc": "t", "date": {"dateval": [1, 1, 1920, False],
                                       "modifier": 0, "quality": 0, "text": ""}}
        assert sync_immich.update_plan({"tags": []}, media, self.MAPPED) == {}

    def test_repoints_changed_file(self):
        a = {"originalPath": "/usr/src/app/upload/upload/u1/new.jpg", "tags": []}
        media = {"desc": "t", "path": "immich/u1/old.jpg"}
        cols = sync_immich.update_plan(a, media, self.MAPPED)
        assert set(cols) == {"file"}
        assert "immich/u1/new.jpg" in cols["file"]

    def test_same_file_no_repoint(self):
        a = {"originalPath": "/usr/src/app/upload/upload/u1/a.jpg", "tags": []}
        media = {"desc": "t", "path": "immich/u1/a.jpg"}
        assert sync_immich.update_plan(a, media, self.MAPPED) == {}

    def test_unmapped_path_hard_fails(self):
        with pytest.raises(SyncError):
            sync_immich.update_plan(
                {"originalPath": "/somewhere/else/a.jpg", "tags": []},
                {"desc": "t", "path": "immich/u1/a.jpg"},
                self.MAPPED,
            )


class TestPlaceHelpers:
    def test_parse_gramps_coord(self):
        assert sync_immich.parse_gramps_coord("N45.5") == 45.5
        assert sync_immich.parse_gramps_coord("W92.9") == -92.9
        assert sync_immich.parse_gramps_coord("45.5") == 45.5
        assert sync_immich.parse_gramps_coord("") is None
        assert sync_immich.parse_gramps_coord("north-ish") is None

    def test_closest_place_respects_250m(self):
        places = [{"lat": "45.0000", "long": "-93.0000", "name": {"value": "Near"}},
                  {"lat": "N45.1000", "long": "W93.1000", "name": {"value": "Far"}}]
        hit = sync_immich.closest_place(45.0001, -93.0001, places)
        assert hit and hit[0]["name"]["value"] == "Near"
        assert sync_immich.closest_place(46.0, -94.0, places) is None


PLACE_CFG = SyncImmichConfig(
    path_mappings=(("/up/", "immich/"),), place_tag_handle="PT", id_tag_prefix="")


def _place(handle="ph1", name="Farmhouse"):
    return {"handle": handle, "gramps_id": "P0001", "lat": "45.0", "long": "-93.0",
            "tag_list": ["PT"], "name": {"value": name}, "media_list": []}


class TestTagScanGates:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        c.execute(
            "INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
            "VALUES ('h-ed', 'uuid-ed', 'Ed', 't')")
        yield c
        c.close()

    def _mint(self, conn, gid, source_id):
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES (?, 'immich', ?, 't', '2026-01-01')", (gid, source_id))
        conn.commit()

    def test_sync_date_gate_drives_an_update(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Date"}]
        a["exifInfo"] = {"dateTimeOriginal": "1955-07-14T10:00:00Z"}
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "t", "path": "immich/img.jpg", "date": None}})
        events = run_scan(im, gr, conn)
        updates = actions(events, "would_update")
        assert len(updates) == 1 and "date" in updates[0].data["cols"]

    def test_ungated_exif_date_is_hands_off(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["exifInfo"] = {"dateTimeOriginal": "1955-07-14T10:00:00Z"}
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "t", "path": "immich/img.jpg", "date": None,
                                    "attribute_list": [
                                        {"type": "Immich ID", "value": "a1"}]}})
        assert actions(run_scan(im, gr, conn), "would_update") == []

    def test_sync_description_gate_drives_a_retitle(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Description"}]
        a["exifInfo"] = {"description": "Grandma at the lake"}
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "img.jpg", "path": "immich/img.jpg"}})
        events = run_scan(im, gr, conn)
        updates = actions(events, "would_update")
        assert len(updates) == 1 and "title" in updates[0].data["cols"]

    def test_sync_location_links_the_closest_place(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Location"}]
        a["exifInfo"] = {"latitude": 45.0001, "longitude": -93.0001}
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps(
            {"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                        "desc": "t", "path": "immich/img.jpg"}},
            places=[_place()])
        preview = run_scan(im, gr, conn, cfg=PLACE_CFG)
        rows = [e for e in preview if e.kind == "item" and e.entity == "place"]
        assert len(rows) == 1 and rows[0].action == "would_update"
        assert gr.updated_places == []
        applied = run_scan(im, gr, conn, apply=True, cfg=PLACE_CFG)
        assert len(gr.updated_places) == 1
        assert gr.updated_places[0]["media_list"][0]["ref"] == "h1"
        assert summary_of(applied).data["places_linked"] == 1

    def test_place_link_is_idempotent(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Location"}]
        a["exifInfo"] = {"latitude": 45.0, "longitude": -93.0}
        place = _place()
        place["media_list"] = [{"ref": "h1"}]
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps(
            {"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                        "desc": "t", "path": "immich/img.jpg"}},
            places=[place])
        events = run_scan(im, gr, conn, apply=True, cfg=PLACE_CFG)
        assert gr.updated_places == []
        assert [e for e in events if e.entity == "place"] == []

    def test_place_only_row_applies_with_its_own_key(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Location"}]
        a["exifInfo"] = {"latitude": 45.0, "longitude": -93.0}
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "t", "path": "immich/img.jpg"}},
                        places=[_place()])
        run_scan(im, gr, conn, apply=True, selected={"place:a1"}, cfg=PLACE_CFG)
        assert len(gr.updated_places) == 1

    def test_create_place_link_is_counted(self, conn):
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Location"}]
        a["exifInfo"] = {"latitude": 45.0, "longitude": -93.0}
        im = FakeImmich(assets={"a1": a}, tagged={"a1"})
        gr = FakeGramps(places=[_place()])
        events = run_scan(im, gr, conn, apply=True, cfg=PLACE_CFG)
        assert summary_of(events).data["places_linked"] == 1
        assert len(gr.updated_places) == 1

    def test_create_uses_description_and_exif_date(self, conn):
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Description"}, {"value": "Sync/Date"},
                     {"value": "date/approximate"}]
        a["exifInfo"] = {"description": "Easter 1966",
                         "dateTimeOriginal": "1966-04-10T00:00:00Z"}
        im = FakeImmich(assets={"a1": a}, tagged={"a1"})
        events = run_scan(im, FakeGramps(), conn)
        creates = actions(events, "would_create")
        assert len(creates) == 1
        assert creates[0].title == "Easter 1966"
        assert "date" in creates[0].data["cols"]


class TestPersonLinksMap:
    def test_empty_table_is_empty(self, tmp_path):
        conn = db.connect(tmp_path / "t.db")
        assert person_links_map(conn) == {}
        conn.close()

    def test_maps_rows(self, tmp_path):
        conn = db.connect(tmp_path / "t.db")
        conn.execute(
            "INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
            "VALUES ('abc123', 'uuid-1', 'Ed Grund', 't'), ('def456', 'uuid-2', NULL, 't')")
        m = person_links_map(conn)
        assert m["uuid-1"] == {"handle": "abc123", "label": "Ed Grund"}
        assert m["uuid-2"]["label"] == ""
        conn.close()


class TestPartnerFaces:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        c.execute(
            "INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
            "VALUES ('h-ed', 'uuid-ed', 'Ed', 't')")
        yield c
        c.close()

    def _cfg(self, tmp_path):
        return SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="")

    def _gramps(self):
        return FakeGramps(people={"h-ed": {"handle": "h-ed", "media_list": []}})

    def test_partner_owned_asset_uses_partner_faces(self, conn, tmp_path):
        a = asset("a1")
        a["ownerId"] = "partner-uid"
        im = FakeImmich(assets={"a1": a}, tagged={"a1"}, me_id="primary-uid")
        partner = FakeImmich(me_id="partner-uid",
                             faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"}}]})
        gr = self._gramps()
        events = run_scan(im, gr, conn, apply=True, cfg=self._cfg(tmp_path), partner=partner)
        assert partner.faces_requested == ["a1"]
        assert im.faces_requested == []
        linked = [e for e in events if e.entity == "face" and e.action == "created"]
        assert len(linked) == 1 and linked[0].title == "Ed"
        assert gr.updated_people[0]["media_list"][0]["ref"] == gr.created[0]["handle"]

    def test_primary_owned_asset_stays_on_the_primary(self, conn, tmp_path):
        a = asset("a1")
        a["ownerId"] = "primary-uid"
        im = FakeImmich(assets={"a1": a}, tagged={"a1"}, me_id="primary-uid",
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"}}]})
        partner = FakeImmich(me_id="partner-uid")
        gr = self._gramps()
        run_scan(im, gr, conn, apply=True, cfg=self._cfg(tmp_path), partner=partner)
        assert im.faces_requested == ["a1"]
        assert partner.faces_requested == []
        assert len(gr.updated_people) == 1

    def test_partner_me_id_resolved_once(self, conn, tmp_path):
        a1, a2 = asset("a1", "x.jpg"), asset("a2", "y.jpg")
        a1["ownerId"] = a2["ownerId"] = "partner-uid"
        im = FakeImmich(assets={"a1": a1, "a2": a2}, tagged={"a1", "a2"}, me_id="primary-uid")
        partner = FakeImmich(me_id="partner-uid")
        run_scan(im, FakeGramps(), conn, apply=True, cfg=self._cfg(tmp_path), partner=partner)
        assert partner.get_me_calls == 1
        assert sorted(partner.faces_requested) == ["a1", "a2"]

    def test_partner_unset_personless_faces_skip_silently(self, conn, tmp_path):
        a = asset("a1")
        a["ownerId"] = "partner-uid"
        im = FakeImmich(assets={"a1": a}, tagged={"a1"},
                        faces={"a1": [{"person": None}, {"id": "f2"}]})
        gr = self._gramps()
        events = run_scan(im, gr, conn, apply=True, cfg=self._cfg(tmp_path))
        assert im.get_me_calls == 0
        assert [e for e in events if e.entity == "face"] == []
        assert gr.updated_people == []
        assert summary_of(events).data["errors"] == 0

    def test_partner_get_me_failure_falls_back_and_surfaces(self, conn, tmp_path):
        class BrokenMe(FakeImmich):
            async def get_me(self):
                raise ImmichError(500, "boom")

        a = asset("a1")
        a["ownerId"] = "partner-uid"
        im = FakeImmich(assets={"a1": a}, tagged={"a1"},
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"}}]})
        partner = BrokenMe(me_id="partner-uid")
        gr = self._gramps()
        events = run_scan(im, gr, conn, apply=True, cfg=self._cfg(tmp_path), partner=partner)
        failed = [e for e in events if e.entity == "face" and e.action == "failed"]
        assert len(failed) == 1 and "partner" in failed[0].detail
        assert im.faces_requested == ["a1"]
        assert partner.faces_requested == []
        assert summary_of(events).data["created"] == 1


class TestTwoAccountScan:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "two.db")
        yield c
        c.close()

    def _run(self, gramps, accounts, conn, **kw):
        async def collect():
            return [e async for e in sync_immich.sync_assets(
                gramps, accounts, conn, CFG, **kw)]
        return asyncio.run(collect())

    def _owned(self, aid, owner, name="img.jpg"):
        a = asset(aid, name)
        a["ownerId"] = owner
        return a

    def test_partner_tagged_asset_is_a_create_candidate(self, conn):
        a = FakeImmich(assets={"a1": self._owned("a1", "user-a")},
                       tagged=set(), me_id="user-a")
        b = FakeImmich(assets={"b1": self._owned("b1", "user-b")},
                       tagged={"b1"}, me_id="user-b")
        events = self._run(FakeGramps(), [a, b], conn)
        creates = actions(events, "would_create")
        assert [e.source_id for e in creates] == ["b1"]

    def test_asset_tagged_in_both_accounts_dedupes(self, conn):
        shared = self._owned("s1", "user-a")
        a = FakeImmich(assets={"s1": shared}, tagged={"s1"}, me_id="user-a")
        b = FakeImmich(assets={"s1": shared}, tagged={"s1"}, me_id="user-b")
        events = self._run(FakeGramps(), [a, b], conn)
        assert len(actions(events, "would_create")) == 1

    def test_missing_tag_in_one_account_warns_and_continues(self, conn):
        a = FakeImmich(assets={"a1": self._owned("a1", "user-a")},
                       tagged={"a1"}, me_id="user-a")
        b = FakeImmich(assets={}, tagged=set(), tag_name="Other/Tag",
                       me_id="user-b")
        events = self._run(FakeGramps(), [a, b], conn)
        assert [e.source_id for e in actions(events, "would_create")] == ["a1"]
        warns = [e for e in actions(events, "skipped")
                 if "trigger tag" in (e.detail or "")]
        assert len(warns) == 1 and "user-b" in warns[0].detail

    def test_missing_tag_everywhere_is_an_error(self, conn):
        a = FakeImmich(assets={}, tagged=set(), tag_name="Nope/A", me_id="user-a")
        b = FakeImmich(assets={}, tagged=set(), tag_name="Nope/B", me_id="user-b")
        with pytest.raises(SyncError) as exc:
            self._run(FakeGramps(), [a, b], conn)
        assert exc.value.status == 400

    def test_stacks_merge_across_accounts(self, conn):
        stacks_b = [{"id": "s1", "primaryAssetId": "p1",
                     "assets": [{"id": "p1"}, {"id": "c1"}]}]
        a = FakeImmich(assets={}, tagged=set(), me_id="user-a")
        b = FakeImmich(assets={"p1": self._owned("p1", "user-b"),
                               "c1": self._owned("c1", "user-b")},
                       stacks=stacks_b, tagged={"p1", "c1"}, me_id="user-b")
        events = self._run(FakeGramps(), [a, b], conn)
        assert [e.source_id for e in actions(events, "would_create")] == ["p1"]
        assert actions(events, "failed") == []

    def test_tags_merge_across_accounts_with_owner_preference(self, conn):
        base = self._owned("m1", "user-b")
        owner_view = {**base, "tags": [{"value": "Sync/Gramps"},
                                       {"value": "Sync/Date"},
                                       {"value": "date/year"}],
                      "exifInfo": {"dateTimeOriginal": "1955-07-14T10:00:00Z"}}
        other_view = {**base, "tags": [{"value": "date/month"}],
                      "exifInfo": {"dateTimeOriginal": "1955-07-14T10:00:00Z"}}
        a = FakeImmich(assets={"m1": other_view}, tagged=set(), me_id="user-a")
        b = FakeImmich(assets={"m1": owner_view}, tagged={"m1"}, me_id="user-b")
        events = self._run(FakeGramps(), [a, b], conn)
        create = actions(events, "would_create")[0]
        assert create.data["cols"]["date"].strip() == "1955"

    def test_faces_read_via_the_owning_account(self, conn):
        conn.execute(
            "INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
            "VALUES ('h-ed', 'uuid-ed', 'Ed', 't')")
        conn.commit()
        a = FakeImmich(assets={"b1": self._owned("b1", "user-b")},
                       tagged=set(), me_id="user-a")
        b = FakeImmich(assets={"b1": self._owned("b1", "user-b")},
                       tagged={"b1"}, me_id="user-b",
                       faces={"b1": [{"person": {"id": "uuid-ed", "name": "Ed"}}]})
        gr = FakeGramps(people={"h-ed": {"handle": "h-ed", "media_list": []}})
        self._run(gr, [a, b], conn, apply=True)
        assert b.faces_requested == ["b1"]
        assert a.faces_requested == []
        assert len(gr.updated_people) == 1


class TestAccountRobustness:

    def test_pick_faces_probes_past_a_broken_first_account(self):
        class BrokenMe(FakeImmich):
            async def get_me(self):
                raise ImmichError(500, "boom")

        broken = BrokenMe(me_id="user-a")
        owner = FakeImmich(me_id="user-b")
        client, err = asyncio.run(sync_immich.owner_client(
            [broken, owner], {"ownerId": "user-b"}))
        assert client is owner and err is None

    def test_pick_faces_falls_back_with_error_when_no_probe_matches(self):
        class BrokenMe(FakeImmich):
            async def get_me(self):
                raise ImmichError(500, "boom")

        a = FakeImmich(me_id="user-a")
        broken = BrokenMe(me_id="user-b")
        client, err = asyncio.run(sync_immich.owner_client(
            [a, broken], {"ownerId": "user-b"}))
        assert client is a and err and "identity lookup failed" in err

    def test_merge_copies_unknown_owner_falls_back_to_plain_union(self):
        copies = [
            ("u1", {"ownerId": "unknown", "tags": [{"value": "date/year"}]}),
            ("u2", {"ownerId": "unknown", "tags": [{"value": "date/month"}]}),
        ]
        merged = sync_immich._merge_copies(copies)
        tags = {t["value"] for t in merged["tags"]}
        assert tags == {"date/year", "date/month"}

    def test_merged_one_mixed_errors_is_a_502_not_a_404(self):
        class Down(FakeImmich):
            async def get_asset(self, asset_id):
                raise ImmichError(0, "request failed")

        with pytest.raises(SyncError) as exc:
            asyncio.run(sync_immich._merged_one(
                [FakeImmich(), Down()], "nope"))
        assert exc.value.status == 502

    def test_merged_one_all_404_stays_404(self):
        with pytest.raises(SyncError) as exc:
            asyncio.run(sync_immich._merged_one(
                [FakeImmich(), FakeImmich(me_id="me-2")], "nope"))
        assert exc.value.status == 404

    def test_merged_one_survives_a_broken_get_me(self):
        class BrokenMe(FakeImmich):
            async def get_me(self):
                raise ImmichError(500, "boom")

        a = asset("a1")
        got = asyncio.run(sync_immich._merged_one(
            [BrokenMe(assets={"a1": a}), FakeImmich(me_id="me-2")], "a1"))
        assert got["id"] == "a1"


class TestIdTags:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "idtag.db")
        yield c
        c.close()

    def _mint(self, conn, gid, source_id):
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES (?, 'immich', ?, 't', '2026-01-01')", (gid, source_id))
        conn.commit()

    def _media(self, gid="BBBBBB", asset_id="a1"):
        return {gid: {"gramps_id": gid, "handle": "h1", "desc": "t",
                      "path": "immich/img.jpg",
                      "attribute_list": [{"type": "Immich ID", "value": asset_id}]}}

    def test_plan_proposes_a_missing_tag(self):
        assert sync_immich.id_tag_plan(asset("a1"), "BBBBBB", ID_CFG) == {"id tag": "ID/BBBBBB"}

    def test_plan_is_quiet_when_the_tag_is_present(self):
        a = asset("a1")
        a["tags"] = [{"value": "ID/BBBBBB"}]
        assert sync_immich.id_tag_plan(a, "BBBBBB", ID_CFG) == {}

    def test_plan_flags_a_stale_id_tag(self):
        a = asset("a1")
        a["tags"] = [{"value": "ID/OLDONE"}]
        cols = sync_immich.id_tag_plan(a, "BBBBBB", ID_CFG)
        assert "ID/BBBBBB" in cols["id tag"] and "replaces" in cols["id tag"]

    def test_plan_disabled_by_empty_prefix(self):
        assert sync_immich.id_tag_plan(asset("a1"), "BBBBBB", CFG) == {}

    def test_plan_skips_when_the_owner_is_unknown(self):
        a = asset("a1")
        a[sync_immich._OWNER_TAGS_KEY] = None
        assert sync_immich.id_tag_plan(a, "BBBBBB", ID_CFG) == {}

    def test_create_tags_via_the_owning_account(self, conn):
        a = asset("a1")
        a["ownerId"] = "user-b"
        fh = FakeImmich(assets={"a1": a}, tagged=set(), me_id="user-a")
        peter = FakeImmich(assets={"a1": a}, tagged={"a1"}, me_id="user-b")
        gr = FakeGramps()
        events = run_scan(fh, gr, conn, apply=True, cfg=ID_CFG, partner=peter)
        gid = gr.created[0]["gramps_id"]
        assert peter.upserted == [f"ID/{gid}"]
        assert fh.upserted == []
        assert peter.tagged_assets == [(peter.extra_tags[f"id/{gid.lower()}"]["id"], "a1")]
        assert [e.action for e in events if e.entity == "tag"] == ["created"]
        assert summary_of(events).data["id_tags_written"] == 1

    def test_tag_present_only_in_the_other_account_still_writes(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        owner_view = asset("a1")
        owner_view["ownerId"] = "user-b"
        other_view = {**owner_view, "tags": [{"value": "ID/BBBBBB"}]}
        fh = FakeImmich(assets={"a1": other_view}, tagged=set(), me_id="user-a")
        peter = FakeImmich(assets={"a1": owner_view}, tagged=set(), me_id="user-b")
        gr = FakeGramps(self._media())
        preview = run_scan(fh, gr, conn, cfg=ID_CFG, partner=peter)
        updates = actions(preview, "would_update")
        assert len(updates) == 1 and updates[0].data["cols"] == {"id tag": "ID/BBBBBB"}
        run_scan(fh, gr, conn, apply=True, cfg=ID_CFG, partner=peter)
        assert peter.upserted == ["ID/BBBBBB"] and fh.upserted == []

    def test_tag_only_change_never_puts_the_media_to_gramps(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1")}, tagged=set())
        gr = FakeGramps(self._media())
        events = run_scan(im, gr, conn, apply=True, cfg=ID_CFG)
        assert im.upserted == ["ID/BBBBBB"]
        assert gr.updated == []
        assert summary_of(events).data["id_tags_written"] == 1

    def test_existing_tag_is_left_alone(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "ID/BBBBBB"}]
        im = FakeImmich(assets={"a1": a}, tagged=set())
        gr = FakeGramps(self._media())
        events = run_scan(im, gr, conn, apply=True, cfg=ID_CFG)
        assert im.upserted == [] and im.tagged_assets == []
        assert summary_of(events).data["skipped"] == 1

    def test_stale_id_tag_is_removed(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "ID/OLDONE"}]
        im = FakeImmich(assets={"a1": a}, tagged=set())
        im.extra_tags["id/oldone"] = {"id": "tag-old", "value": "ID/OLDONE", "name": "OLDONE"}
        gr = FakeGramps(self._media())
        run_scan(im, gr, conn, apply=True, cfg=ID_CFG)
        assert im.upserted == ["ID/BBBBBB"]
        assert im.untagged_assets == [("tag-old", "a1")]

    def test_preview_writes_no_tags(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1")}, tagged=set())
        gr = FakeGramps(self._media())
        run_scan(im, gr, conn, cfg=ID_CFG)
        assert im.upserted == [] and im.tagged_assets == []

    def test_tag_write_failure_is_best_effort(self, conn):
        im = FakeImmich(assets={"a1": asset("a1")}, tagged={"a1"})
        im.fail_tag_write = True
        gr = FakeGramps()
        events = run_scan(im, gr, conn, apply=True, cfg=ID_CFG)
        assert len(gr.created) == 1
        failed = [e for e in events if e.entity == "tag" and e.action == "failed"]
        assert len(failed) == 1 and "boom" in failed[0].detail
        assert summary_of(events).data["created"] == 1
        assert summary_of(events).data["errors"] == 1

    def test_disabled_prefix_writes_nothing(self, conn):
        im = FakeImmich(assets={"a1": asset("a1")}, tagged={"a1"})
        run_scan(im, FakeGramps(), conn, apply=True, cfg=CFG)
        assert im.upserted == []


class TestSyncEnabledKnob:
    def _cfg(self, tmp_path, immich_block):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "gramps: {base_url: x, username: u, password: p}\n"
            "paperless: {base_url: x, api_token: t}\n"
            f"sync:\n  immich:\n    {immich_block}\n"
        )
        from bifrost.core.config import load_config
        return load_config(cfg)

    def test_absent_means_enabled(self, tmp_path):
        assert self._cfg(tmp_path, "public_url: x").sync_immich.enabled is True

    def test_explicit_false(self, tmp_path):
        assert self._cfg(tmp_path, "enabled: false").sync_immich.enabled is False

    def test_sync_tag_defaults_and_overrides(self, tmp_path):
        assert self._cfg(tmp_path, "public_url: x").sync_immich.sync_tag == "Sync/Gramps"
        assert self._cfg(tmp_path, 'sync_tag: "Gramps/Queue"').sync_immich.sync_tag == "Gramps/Queue"

    def test_sync_tag_whitespace_stripped(self, tmp_path):
        assert self._cfg(tmp_path, 'sync_tag: "Sync/Gramps  "').sync_immich.sync_tag == "Sync/Gramps"

    def test_id_tag_prefix_defaults_on(self, tmp_path):
        assert self._cfg(tmp_path, "public_url: x").sync_immich.id_tag_prefix == "ID"

    def test_id_tag_prefix_empty_disables(self, tmp_path):
        assert self._cfg(tmp_path, 'id_tag_prefix: ""').sync_immich.id_tag_prefix == ""

    def test_id_tag_prefix_custom_and_normalized(self, tmp_path):
        assert self._cfg(tmp_path, 'id_tag_prefix: "Gramps/"').sync_immich.id_tag_prefix == "Gramps"


class TestFaceRects:
    FACE = {"boundingBoxX1": 1104, "boundingBoxY1": 644,
            "boundingBoxX2": 1205, "boundingBoxY2": 772,
            "imageWidth": 2312, "imageHeight": 1440}

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        c.execute(
            "INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
            "VALUES ('h-ed', 'uuid-ed', 'Ed', 't')")
        yield c
        c.close()

    def _cfg(self, tmp_path):
        return SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="")

    def test_face_rect_math(self):
        assert sync_immich._face_rect(self.FACE, pad=False) == [48, 45, 52, 54]
        assert sync_immich._face_rect(self.FACE, pad=True) == [47, 43, 53, 55]
        assert sync_immich._face_rect({**self.FACE, "imageWidth": 0}) == []
        assert sync_immich._face_rect(
            {**self.FACE, "boundingBoxX2": self.FACE["boundingBoxX1"]}) == []
        near_edge = {"boundingBoxX1": 5, "boundingBoxY1": 5,
                     "boundingBoxX2": 100, "boundingBoxY2": 100,
                     "imageWidth": 100, "imageHeight": 100}
        assert all(0 <= v <= 100 for v in sync_immich._face_rect(near_edge, pad=True))

    def test_new_link_gets_padded_rect(self, conn, tmp_path):
        im = FakeImmich(assets={"a1": asset("a1")}, tagged={"a1"},
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                       **self.FACE}]})
        gr = FakeGramps(people={"h-ed": {"handle": "h-ed", "media_list": []}})
        run_scan(im, gr, conn, apply=True, cfg=self._cfg(tmp_path))
        ref = gr.updated_people[0]["media_list"][0]
        assert ref["rect"] == [47, 43, 53, 55]

    def test_manual_faces_tag_gives_tight_rect(self, conn, tmp_path):
        a = asset("a1")
        a["tags"] = [{"value": "Sync/ManualFaces"}]
        im = FakeImmich(assets={"a1": a}, tagged={"a1"},
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                       **self.FACE}]})
        gr = FakeGramps(people={"h-ed": {"handle": "h-ed", "media_list": []}})
        run_scan(im, gr, conn, apply=True, cfg=self._cfg(tmp_path))
        assert gr.updated_people[0]["media_list"][0]["rect"] == [48, 45, 52, 54]

    def _resume(self, im, gr, conn, cfg):
        async def collect():
            return [e async for e in sync_immich.sync_one_asset(
                gr, [im], conn, cfg, "a1")]
        return asyncio.run(collect())

    def test_empty_rect_healed_on_resync(self, conn, tmp_path):
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES ('BBBBBB', 'immich', 'a1', 'T', '2026-01-01')")
        conn.commit()
        im = FakeImmich(assets={"a1": asset("a1")},
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                       **self.FACE}]})
        gr = FakeGramps(
            media={"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                              "desc": "T", "path": "immich/img.jpg"}},
            people={"h-ed": {"handle": "h-ed", "media_list": [
                {"_class": "MediaRef", "ref": "h1", "rect": []}]}})
        events = self._resume(im, gr, conn, self._cfg(tmp_path))
        assert gr.updated_people[0]["media_list"][0]["rect"] == [47, 43, 53, 55]
        assert [e.action for e in events if e.entity == "face"] == ["updated"]

    def test_hand_set_rect_never_touched(self, conn, tmp_path):
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES ('BBBBBB', 'immich', 'a1', 'T', '2026-01-01')")
        conn.commit()
        im = FakeImmich(assets={"a1": asset("a1")},
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                       **self.FACE}]})
        gr = FakeGramps(
            media={"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                              "desc": "T", "path": "immich/img.jpg"}},
            people={"h-ed": {"handle": "h-ed", "media_list": [
                {"_class": "MediaRef", "ref": "h1", "rect": [10, 10, 50, 50]}]}})
        events = self._resume(im, gr, conn, self._cfg(tmp_path))
        assert gr.updated_people == []
        assert gr.people["h-ed"]["media_list"][0]["rect"] == [10, 10, 50, 50]
        assert [e.action for e in events if e.entity == "face"] == []
