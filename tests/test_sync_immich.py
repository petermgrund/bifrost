import asyncio

import pytest

from bifrost.core import db
from bifrost.core.clients.gramps import GrampsClient, GrampsError
from bifrost.core.clients.immich import ImmichError
from bifrost.core.config import SyncImmichConfig
from bifrost.modules import sync_immich
from bifrost.modules.sync_immich import PERSON_ATTR, SyncError, translate_path

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
        self.previews = {}
        self.upserted = []
        self.tagged_assets = []
        self.untagged_assets = []
        self.fail_tag_write = False
        self.metadata = {}
        self.updated_assets = []
        self.bulk_tagged = []

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
        await self.tag_assets([tag_id], [asset_id])

    def _tag_value(self, tag_id):
        for t in [self.tag] + list(self.extra_tags.values()):
            if t["id"] == tag_id:
                return t["value"]
        return None

    async def untag_asset(self, tag_id, asset_id):
        self.untagged_assets.append((tag_id, asset_id))
        value = self._tag_value(tag_id)
        a = self.assets.get(asset_id)
        if a is not None and value:
            a["tags"] = [t for t in a.get("tags") or [] if t.get("value", "").lower() != value.lower()]

    def _known(self, value):
        tag = self.extra_tags.get(value.lower())
        if tag is None and value.lower() != self.tag["value"].lower():
            tag = {"id": f"tag-{len(self.extra_tags) + 2}", "name": value.split("/")[-1], "value": value}
            self.extra_tags[value.lower()] = tag
        return tag

    async def list_tags(self):
        for a in self.assets.values():
            for t in a.get("tags") or []:
                if t.get("value"):
                    self._known(t["value"])
        return [self.tag] + list(self.extra_tags.values())

    async def tag_assets(self, tag_ids, asset_ids):
        self.bulk_tagged.append((list(tag_ids), list(asset_ids)))
        for asset_id in asset_ids:
            a = self.assets.get(asset_id)
            if a is None:
                continue
            have = {t.get("value", "").lower() for t in a.get("tags") or []}
            for tag_id in tag_ids:
                value = self._tag_value(tag_id)
                if value and value.lower() not in have:
                    a.setdefault("tags", []).append({"value": value})

    async def update_asset(self, asset_id, **fields):
        self.updated_assets.append((asset_id, fields))
        a = self.assets[asset_id]
        if "description" in fields:
            a.setdefault("exifInfo", {})["description"] = fields["description"]
        if "dateTimeOriginal" in fields:
            a["localDateTime"] = fields["dateTimeOriginal"]
        for key in ("latitude", "longitude"):
            if key in fields:
                a.setdefault("exifInfo", {})[key] = fields[key]
        return a

    async def get_asset_metadata(self, asset_id):
        return dict(self.metadata.get(asset_id, {}))

    async def upsert_asset_metadata(self, asset_id, key, value):
        self.metadata.setdefault(asset_id, {})[key] = value

    async def delete_asset_metadata(self, asset_id, key):
        self.metadata.get(asset_id, {}).pop(key, None)

    async def get_stack(self, stack_id):
        for s in self.stacks:
            if s["id"] == stack_id:
                return s
        raise ImmichError(400, "no such stack")

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

    async def preview_file(self, asset_id):
        return self.previews.get(asset_id)

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
        self.notes = {}
        self.updated_notes = []
        self.deleted_notes = []
        self.checksums = {}
        self.unreadable = set()
        self.list_people_calls = 0
        self.list_ids_calls = 0

    async def list_people(self, keys=None):
        self.list_people_calls += 1
        return list(self.people.values())

    async def list_media(self, keys=None):
        return list(self.media.values())

    async def get_media_by_gramps_id(self, gid, backlinks=False):
        media = self.media.get(gid)
        if media is not None:
            media.setdefault("checksum", f"md5-{media.get('handle')}")
            if backlinks:
                holders = [p["handle"] for p in self.places
                           if any(r.get("ref") == media.get("handle") for r in p.get("media_list") or [])]
                return {**media, "backlinks": {"place": holders}}
        return media

    async def get_note(self, handle):
        return self.notes.get(handle)

    async def delete_note(self, handle):
        self.deleted_notes.append(handle)
        self.notes.pop(handle, None)

    async def get_place(self, handle):
        return next(p for p in self.places if p.get("handle") == handle)

    async def media_md5(self, handle):
        path = next((m.get("path") for m in self.media.values() if m.get("handle") == handle), None)
        if path in self.unreadable:
            raise GrampsError(f"GET /media/{handle}/file → 404: not found")
        return self.checksums.get(handle, f"md5-{handle}")

    store_checksum = GrampsClient.store_checksum

    async def get_place_by_gramps_id(self, gid):
        return next((p for p in self.places if p.get("gramps_id") == gid), None)

    async def _paged(self, path, page_size=200, **params):
        assert path == "/notes/"
        return [{"gramps_id": n["gramps_id"]} for n in self.notes.values()]

    async def create_note(self, obj):
        self.notes[obj["handle"]] = obj

    async def update_note(self, handle, obj):
        self.notes[handle] = obj
        self.updated_notes.append(obj)

    async def list_media_gramps_ids(self):
        self.list_ids_calls += 1
        return set(self.media)

    async def create_media(self, obj):
        self.media[obj["gramps_id"]] = obj
        self.created.append(obj)

    async def update_media(self, handle, obj):
        obj["change"] = (obj.get("change") or 0) + 1
        self.updated.append(obj)
        if obj.get("gramps_id") in self.media:
            self.media[obj["gramps_id"]] = obj

    async def list_places_full(self):
        return self.places

    async def update_place(self, handle, place_obj):
        self.updated_places.append(place_obj)

    async def get_person(self, handle, ok_404=False):
        if handle not in self.people:
            if ok_404:
                return None
            raise GrampsError(f"GET /people/{handle} → 404")
        return self.people[handle]

    async def get_media_backlinks(self, handle):
        return {"person": [h for h, p in self.people.items()
                           if any(r.get("ref") == handle for r in p.get("media_list") or [])]}

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


PREVIEW_CFG = SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="",
                               previews_prefix="immich-previews/")
PREVIEW_PATH = "immich-previews/owner-1/a1/b2/a1b2c3_preview.jpeg"


def heic(aid="a1b2c3", name="img.heic", owner="owner-1"):
    return {**asset(aid, name), "originalMimeType": "image/heic", "ownerId": owner}


def titled(a, title="t"):
    """An asset whose Immich description already mirrors its Gramps title"""
    a.setdefault("exifInfo", {})["description"] = title
    return a


def mint(conn, gid, source_id, system="immich"):
    conn.execute(
        "INSERT INTO minted_media (gramps_id, source_system, source_id, created_at, minted_at) "
        "VALUES (?, ?, ?, '2026-01-01', '2026-01-01')", (gid, system, source_id))
    conn.commit()


def linked(handle, *person_ids, media_list=()):
    """A Gramps person carrying Immich Person ID attributes"""
    return {"handle": handle, "media_list": list(media_list),
            "attribute_list": [{"type": PERSON_ATTR, "value": pid} for pid in person_ids]}


class TestPreviews:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        yield c
        c.close()

    def test_web_images_keep_the_original(self):
        a = {**asset("a1", "img.jpg"), "ownerId": "owner-1"}
        assert sync_immich.gramps_file(a, PREVIEW_CFG) == ("immich/img.jpg", "image/jpeg")

    def test_without_a_previews_prefix_the_original_is_linked(self):
        assert sync_immich.gramps_file(heic(), CFG) == ("immich/img.heic", "image/heic")

    def test_preview_path_follows_immich_layout(self):
        assert sync_immich.gramps_file(heic(), PREVIEW_CFG, ("jpeg", "image/jpeg")) == (
            PREVIEW_PATH, "image/jpeg")
        assert sync_immich.gramps_file(heic(), PREVIEW_CFG, ("webp", "image/webp")) == (
            "immich-previews/owner-1/a1/b2/a1b2c3_preview.webp", "image/webp")

    def test_missing_preview_is_an_error(self):
        with pytest.raises(SyncError, match="no preview"):
            sync_immich.gramps_file(heic(), PREVIEW_CFG)

    def test_create_links_the_preview(self, conn):
        im = FakeImmich(assets={"a1b2c3": heic()}, tagged={"a1b2c3"})
        im.previews["a1b2c3"] = ("jpeg", "image/jpeg")
        gr = FakeGramps()
        run_scan(im, gr, conn, apply=True, cfg=PREVIEW_CFG)
        assert gr.created[0]["path"] == PREVIEW_PATH
        assert gr.created[0]["mime"] == "image/jpeg"

    def test_synced_heic_media_is_repointed_at_the_preview(self, conn):
        mint(conn, "BBBBBB", "a1b2c3")
        im = FakeImmich(assets={"a1b2c3": {**heic(), "exifInfo": {"description": "T"}}})
        im.previews["a1b2c3"] = ("jpeg", "image/jpeg")
        media = {"gramps_id": "BBBBBB", "handle": "h1", "desc": "T", "path": "immich/img.heic",
                 "mime": "image/heic", "attribute_list": [sync_immich._attr("Immich ID", "a1b2c3")]}
        events = run_scan(im, FakeGramps({"BBBBBB": media}), conn, cfg=PREVIEW_CFG)
        rows = actions(events, "would_update")
        assert len(rows) == 1
        assert rows[0].data["cols"] == {"file": f"immich/img.heic → {PREVIEW_PATH}"}
        gr = FakeGramps({"BBBBBB": dict(media)})
        run_scan(im, gr, conn, apply=True, cfg=PREVIEW_CFG)
        assert (gr.updated[0]["path"], gr.updated[0]["mime"]) == (PREVIEW_PATH, "image/jpeg")

    def test_preview_not_generated_yet_fails_the_row(self, conn):
        im = FakeImmich(assets={"a1b2c3": heic()}, tagged={"a1b2c3"})
        gr = FakeGramps()
        events = run_scan(im, gr, conn, apply=True, cfg=PREVIEW_CFG)
        assert gr.created == []
        assert "no preview" in actions(events, "failed")[0].detail


def summary_of(events):
    return [e for e in events if e.kind == "summary"][-1]


class TestSyncAssetsScan:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        yield c
        c.close()

    def _mint(self, conn, gid, source_id):
        mint(conn, gid, source_id)

    def test_progress_is_one_running_count_over_every_item(self, conn):
        self._mint(conn, "K1", "a2")
        im = FakeImmich(assets={"a1": asset("a1"), "a2": asset("a2")}, tagged={"a1"})
        gr = FakeGramps(media={"K1": {"gramps_id": "K1", "handle": "mh", "desc": "t",
                                      "path": "immich/img.jpg", "mime": "image/jpeg"}})
        events = run_scan(im, gr, conn)
        progress = [e for e in events if e.kind == "progress"]
        # 2 details + 1 tagged + 1 synced = 4 items, one total throughout
        assert {p.data["total"] for p in progress} == {4}
        dones = [p.data["done"] for p in progress]
        assert dones == sorted(dones) and dones[0] == 0 and dones[-1] == 4
        assert [p.detail for p in progress] == ["Reading photo details", "Checking new photos",
                                                "Checking synced media", "Checking synced media"]
        assert events.index(next(e for e in events if e.kind == "summary")) > events.index(progress[-1])

    def test_tagged_unsynced_is_a_create_candidate(self, conn):
        im = FakeImmich(assets={"a1": asset("a1", "img1.jpg")}, tagged={"a1"})
        events = run_scan(im, FakeGramps(), conn)
        creates = actions(events, "would_create")
        assert [e.source_id for e in creates] == ["a1"]
        assert creates[0].title == "img1.jpg"
        assert creates[0].data == {"cols": {"title": "img1.jpg"}}

    def test_a_batch_lists_people_and_ids_once(self, conn):
        im = FakeImmich(assets={"a1": asset("a1", "x.jpg"), "a2": asset("a2", "y.jpg")}, tagged={"a1", "a2"})
        gr = FakeGramps(people={"h-ed": linked("h-ed", "uuid-ed")})
        preview = run_scan(im, gr, conn)
        assert (gr.list_people_calls, gr.list_ids_calls) == (0, 0)
        run_scan(im, gr, conn, apply=True)
        assert len(gr.created) == 2
        assert (gr.list_people_calls, gr.list_ids_calls) == (1, 1)
        assert len({m["gramps_id"] for m in gr.created}) == 2
        assert len(preview) > 0

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

    def test_synced_media_gets_the_gramps_title_as_its_description(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1", "img.jpg")
        a["tags"] = [{"value": "Sync/Description"}]
        a["exifInfo"] = {"description": "Immich title"}
        im = FakeImmich(assets={"a1": a}, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "Gramps title", "path": "immich/img.jpg",
                                    "attribute_list": [
                                        {"type": "Immich ID", "value": "a1"}]}})
        events = run_scan(im, gr, conn)
        updates = actions(events, "would_update")
        assert len(updates) == 1 and set(updates[0].data["cols"]) == {"description"}
        events = run_scan(im, gr, conn, apply=True)
        assert gr.updated == []
        assert im.updated_assets == [("a1", {"description": "Gramps title"})]
        assert summary_of(events).data["descriptions_updated"] == 1
        assert actions(run_scan(im, gr, conn), "would_update") == []

    def test_minted_media_carry_the_md5_of_their_file(self, conn):
        im = FakeImmich(assets={"a1": asset("a1", "img1.jpg")}, tagged={"a1"})
        gr = FakeGramps()
        run_scan(im, gr, conn, apply=True)
        media = gr.created[0]
        assert media["checksum"] == f"md5-{media['handle']}"

    def test_a_file_gramps_cannot_read_is_reported_at_mint(self, conn):
        im = FakeImmich(assets={"a1": asset("a1", "img1.jpg")}, tagged={"a1"})
        gr = FakeGramps()
        gr.unreadable.add("immich/img1.jpg")
        events = run_scan(im, gr, conn, apply=True)
        failed = actions(events, "failed")
        assert len(failed) == 1 and "could not read its file" in failed[0].detail
        assert len(gr.created) == 1 and not gr.created[0].get("checksum")

    def test_a_missing_checksum_is_filled_by_the_update_pass(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": titled(asset("a1", "img.jpg"))}, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1", "desc": "t",
                                    "path": "immich/img.jpg", "checksum": "",
                                    "attribute_list": [{"type": "Immich ID", "value": "a1"}]}})
        preview = run_scan(im, gr, conn)
        assert [u.data["cols"] for u in actions(preview, "would_update")] == [{"checksum": "missing"}]
        run_scan(im, gr, conn, apply=True)
        assert len(gr.updated) == 1 and gr.updated[0]["checksum"] == "md5-h1"

    def test_a_repointed_file_gets_a_fresh_checksum(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1", "new.jpg")}, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1", "desc": "t",
                                    "path": "immich/old.jpg", "checksum": "old-md5",
                                    "attribute_list": [{"type": "Immich ID", "value": "a1"}]}})
        gr.checksums["h1"] = "new-md5"
        run_scan(im, gr, conn, apply=True)
        media = gr.media["BBBBBB"]
        assert (media["path"], media["checksum"], len(gr.updated)) == ("immich/new.jpg", "new-md5", 2)

    def test_an_unreadable_new_file_leaves_the_checksum_missing_for_the_next_scan(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1", "new.jpg")}, tagged=set())
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1", "desc": "t",
                                    "path": "immich/old.jpg", "checksum": "old-md5",
                                    "attribute_list": [{"type": "Immich ID", "value": "a1"}]}})
        gr.unreadable.add("immich/new.jpg")
        events = run_scan(im, gr, conn, apply=True)
        assert ["new file" in e.detail for e in actions(events, "failed")] == [True]
        preview = run_scan(im, gr, conn)
        assert [u.data["cols"] for u in actions(preview, "would_update")] == [{"checksum": "missing"}]

    def test_stale_immich_attrs_heal_without_a_file_move(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": titled(asset("a1", "img.jpg"))}, tagged=set())
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
        im = FakeImmich(assets={"a1": titled(asset("a1", "img.jpg"))}, tagged={"a1"})
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
            assets={"new1": titled(asset("new1", "new.jpg"), "T"), "old1": asset("old1", "old.jpg")},
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
        assert len(gr.updated) == 2
        media = gr.updated[0]
        assert media["path"] == "immich/new.jpg" and media["checksum"] == "md5-h1"
        assert media["desc"] == "T"
        attrs = {a["type"]: a["value"] for a in media["attribute_list"]}
        assert attrs["Immich ID"] == "new1"
        row = conn.execute(
            "SELECT source_id FROM minted_media WHERE gramps_id='BBBBBB'").fetchone()
        assert row["source_id"] == "new1"
        assert summary_of(events).data["versions_updated"] == 1

    def test_apply_leaves_the_gramps_title_and_date_alone(self, conn):
        self._mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["tags"] = [{"value": "Sync/Description"}, {"value": "Sync/Date"}]
        a["exifInfo"] = {"description": "Immich title",
                         "dateTimeOriginal": "1955-07-14T10:00:00Z"}
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "Gramps title", "path": "immich/img.jpg",
                                    "date": None, "attribute_list": [{"type": "Immich ID", "value": "a1"}]}})
        events = run_scan(im, gr, conn, apply=True)
        assert gr.updated == []
        assert gr.media["BBBBBB"]["date"] is None
        assert im.updated_assets == [("a1", {"description": "Gramps title"})]
        s = summary_of(events).data
        assert s["descriptions_updated"] == 1 and s["errors"] == 0

    def test_moved_main_with_tagged_metadata_updates_the_file_only(self, conn):
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
        assert set(updates[0].data["cols"]) == {"file", "link", "description"}
        run_scan(im, gr, conn, apply=True)
        media = gr.updated[0]
        assert media["path"] == "immich/new.jpg"
        assert media["desc"] == "T" and media["date"] is None
        assert new1["exifInfo"]["description"] == "T"
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
        assert len(gr.updated) == 2 and gr.updated[0]["path"] == "immich/new.jpg"
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

    def test_apply_register_conflict_is_a_failed_row(self, conn):
        im = FakeImmich(assets={"a1": asset("a1", "img1.jpg")}, tagged={"a1"})
        events = run_scan(im, RacingGramps(conn), conn, apply=True)
        failed = actions(events, "failed")
        assert len(failed) == 1 and "not registered" in failed[0].detail
        assert summary_of(events).data["created"] == 0
        assert summary_of(events).data["errors"] == 1
        assert [r["source_id"] for r in conn.execute(
            "SELECT source_id FROM minted_media WHERE source_system IS NOT NULL")] == ["202"]


def test_sync_counts_are_all_initialized():
    import inspect
    import re

    init = inspect.getsource(sync_immich.new_counts)
    declared = set(re.findall(r"\"(\w+)\"\s*:", init))
    src = (inspect.getsource(sync_immich.sync_assets)
           + inspect.getsource(sync_immich.update_synced)
           + inspect.getsource(sync_immich.sync_one_asset))
    used = set(re.findall(r"counts\[\"(\w+)\"\]", src))
    assert used <= declared, f"uninitialized counts keys: {used - declared}"


class TestSyncOneAsset:
    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        yield c
        c.close()

    def _run(self, im, gr, conn, asset_id, gramps_id=None):
        async def collect():
            return [e async for e in sync_immich.sync_one_asset(
                gr, [im], conn, CFG, asset_id, gramps_id=gramps_id)]
        return asyncio.run(collect())

    def test_create_titles_by_file_name_and_seeds_nothing_else(self, conn):
        a = asset("a1", "img.jpg")
        a["tags"] = [{"value": "Sync/Gramps"}, {"value": "Holiday"}]
        a["exifInfo"] = {"description": "Easter 1966", "latitude": 45.0, "longitude": -93.0}
        a["localDateTime"] = "1966-04-10T09:00:00Z"
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps(places=[{"handle": "ph1", "gramps_id": "P0001", "lat": "45.0", "long": "-93.0",
                                 "name": {"value": "Farm"}, "media_list": []}])
        events = self._run(im, gr, conn, "a1")
        summary = summary_of(events)
        assert summary.data["created"] is True
        assert summary.data["title"] == "img.jpg"
        assert "date" not in gr.created[0] and gr.updated_places == []
        assert {a["type"] for a in gr.created[0]["attribute_list"]} == {"Immich ID"}
        row = conn.execute(
            "SELECT gramps_id, created_at, minted_at FROM minted_media WHERE source_id='a1'").fetchone()
        assert row["gramps_id"] == summary.data["gramps_id"] and row["created_at"] == row["minted_at"]

    def test_rerun_resumes_via_register_only(self, conn):
        mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1")})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                                    "desc": "T", "path": "immich/img.jpg"}})
        events = self._run(im, gr, conn, "a1")
        assert gr.created == []
        assert summary_of(events).data["created"] is False
        assert len(actions(events, "skipped")) == 1

    def test_primary_of_registered_variant_resumes_not_mints(self, conn):
        mint(conn, "BBBBBB", "c1")
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
        rows = conn.execute("SELECT source_id FROM minted_media WHERE source_system IS NOT NULL").fetchall()
        assert [r["source_id"] for r in rows] == ["c1"]

    def test_two_register_rows_through_the_stack_error(self, conn):
        mint(conn, "G1G1G1", "c1")
        mint(conn, "G2G2G2", "c2")
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

    def _issued_before(self, conn):
        mint(conn, "XJ4DBT", "101", system="paperless")
        mint(conn, "MNTD22", "a9")
        conn.execute("INSERT INTO minted_media (gramps_id, created_at) VALUES ('RSVD22', 't')")
        conn.execute("INSERT INTO minted_media (gramps_id, created_at, withdrawn_at, withdrawn_reason) "
                     "VALUES ('WDRN22', 't', 't', 'lost')")
        conn.commit()

    def test_create_never_reissues_a_deleted_reserved_or_withdrawn_id(self, conn, script_ids):
        self._issued_before(conn)
        script_ids("XJ4DBT", "RSVD22", "MNTD22", "WDRN22", "FRESH2")
        gr = FakeGramps()
        events = self._run(FakeImmich(assets={"a1": asset("a1")}), gr, conn, "a1")
        assert summary_of(events).data["gramps_id"] == "FRESH2"
        assert [m["gramps_id"] for m in gr.created] == ["FRESH2"]
        row = conn.execute("SELECT source_id FROM minted_media WHERE gramps_id='XJ4DBT'").fetchone()
        assert row["source_id"] == "101"

    def test_manual_id_issued_before_is_rejected(self, conn):
        self._issued_before(conn)
        gr = FakeGramps()
        for gid in ("xj4dbt", "MNTD22", "WDRN22"):
            with pytest.raises(SyncError) as exc:
                self._run(FakeImmich(assets={"a1": asset("a1")}), gr, conn, "a1", gramps_id=gid)
            assert exc.value.status == 400 and "issued before" in exc.value.detail
        assert gr.created == []

    def test_manual_id_refuses_guarded_shapes(self, conn):
        gr = FakeGramps()
        for gid in ("B2C3F4", "222222", "README"):
            with pytest.raises(SyncError) as exc:
                self._run(FakeImmich(assets={"a1": asset("a1")}), gr, conn, "a1", gramps_id=gid)
            assert exc.value.status == 400 and "never issued" in exc.value.detail
        assert gr.created == []

    def test_manual_id_claims_its_open_reservation(self, conn):
        self._issued_before(conn)
        events = self._run(FakeImmich(assets={"a1": asset("a1")}), FakeGramps(), conn, "a1",
                           gramps_id="RSVD22")
        assert summary_of(events).data["gramps_id"] == "RSVD22"
        row = conn.execute(
            "SELECT source_system, source_id, created_at, minted_at FROM minted_media WHERE gramps_id='RSVD22'"
        ).fetchone()
        assert (row["source_system"], row["source_id"], row["created_at"]) == ("immich", "a1", "t")
        assert row["minted_at"] and row["minted_at"] != "t"

    def test_register_conflict_fails_without_overwriting(self, conn):
        self._issued_before(conn)
        gr = RacingGramps(conn)
        with pytest.raises(SyncError) as exc:
            self._run(FakeImmich(assets={"a1": asset("a1")}), gr, conn, "a1", gramps_id="RSVD22")
        assert exc.value.status == 409 and "paperless 202" in exc.value.detail
        row = conn.execute(
            "SELECT source_system, source_id FROM minted_media WHERE gramps_id='RSVD22'").fetchone()
        assert tuple(row) == ("paperless", "202")


class RacingGramps(FakeGramps):
    """Another mint registers the same id while Gramps creates the media"""

    def __init__(self, conn, **kw):
        super().__init__(**kw)
        self.conn = conn

    async def create_media(self, obj):
        await super().create_media(obj)
        self.conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, created_at, minted_at) "
            "VALUES (?, 'paperless', '202', '2026-01-01', '2026-01-01') ON CONFLICT(gramps_id) DO UPDATE SET "
            "source_system='paperless', source_id='202', minted_at='2026-01-01'", (obj["gramps_id"],))
        self.conn.commit()


class TestUpdatePlan:
    MAPPED = SyncImmichConfig(path_mappings=(("/usr/src/app/upload/upload/", "immich/"),))

    def test_title_and_date_are_not_the_syncs_business(self):
        a = {"originalFileName": "img_0001.jpg",
             "exifInfo": {"description": "Grandma, 1920",
                          "dateTimeOriginal": "1920-06-01T10:00:00Z"},
             "tags": [{"value": "Sync/Description"}, {"value": "Sync/Date"}]}
        media = {"desc": "img_0001.jpg", "date": None, "checksum": "c"}
        assert sync_immich.update_plan(a, media, self.MAPPED) == {}

    def test_in_sync(self):
        a = {"exifInfo": {"description": "T",
                          "dateTimeOriginal": "1955-07-14T10:00:00Z"},
             "tags": [{"value": "Sync/Description"}, {"value": "Sync/Date"}]}
        media = {"desc": "T", "checksum": "c", "date": {"dateval": [14, 7, 1955, False],
                                                        "modifier": 0, "quality": 0, "text": ""}}
        assert sync_immich.update_plan(a, media, self.MAPPED) == {}

    def test_never_clears_gramps_date(self):
        media = {"desc": "t", "checksum": "c", "date": {"dateval": [1, 1, 1920, False],
                                                        "modifier": 0, "quality": 0, "text": ""}}
        assert sync_immich.update_plan({"tags": []}, media, self.MAPPED) == {}

    def test_repoints_changed_file(self):
        a = {"originalPath": "/usr/src/app/upload/upload/u1/new.jpg", "tags": []}
        media = {"desc": "t", "path": "immich/u1/old.jpg", "checksum": "c"}
        cols = sync_immich.update_plan(a, media, self.MAPPED)
        assert set(cols) == {"file"}
        assert "immich/u1/new.jpg" in cols["file"]

    def test_same_file_no_repoint(self):
        a = {"originalPath": "/usr/src/app/upload/upload/u1/a.jpg", "tags": []}
        media = {"desc": "t", "path": "immich/u1/a.jpg", "checksum": "c"}
        assert sync_immich.update_plan(a, media, self.MAPPED) == {}

    def test_missing_checksum_is_a_column(self):
        a = {"originalPath": "/usr/src/app/upload/upload/u1/a.jpg", "tags": []}
        media = {"desc": "t", "path": "immich/u1/a.jpg", "checksum": ""}
        assert sync_immich.update_plan(a, media, self.MAPPED) == {"checksum": "missing"}

    def test_unmapped_path_hard_fails(self):
        with pytest.raises(SyncError):
            sync_immich.update_plan(
                {"originalPath": "/somewhere/else/a.jpg", "tags": []},
                {"desc": "t", "path": "immich/u1/a.jpg"},
                self.MAPPED,
            )


class TestImmichFieldsStayInImmich:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        yield c
        c.close()

    def test_the_immich_description_and_date_never_change_the_media(self, conn):
        mint(conn, "BBBBBB", "a1")
        a = asset("a1")
        a["exifInfo"] = {"description": "Grandma at the lake", "dateTimeOriginal": "1955-07-14T10:00:00Z"}
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1", "date": None,
                                    "desc": "Grandma, 1920", "path": "immich/img.jpg",
                                    "attribute_list": [{"type": "Immich ID", "value": "a1"}]}})
        events = run_scan(im, gr, conn)
        updates = actions(events, "would_update")
        assert len(updates) == 1 and set(updates[0].data["cols"]) == {"description"}
        run_scan(im, gr, conn, apply=True)
        assert gr.updated == [] and gr.media["BBBBBB"]["date"] is None
        assert a["exifInfo"]["description"] == "Grandma, 1920"

    def test_gps_and_the_description_seed_nothing_on_create(self, conn):
        a = asset("a1", "img.jpg")
        a["exifInfo"] = {"description": "Easter 1966", "latitude": 45.0, "longitude": -93.0,
                         "dateTimeOriginal": "1966-04-10T00:00:00Z"}
        im = FakeImmich(assets={"a1": a}, tagged={"a1"})
        gr = FakeGramps(places=[{"handle": "ph1", "gramps_id": "P0001", "lat": "45.0", "long": "-93.0",
                                 "name": {"value": "Farm"}, "media_list": []}])
        events = run_scan(im, gr, conn, apply=True)
        assert actions(events, "created")[0].title == "img.jpg"
        assert gr.created[0]["desc"] == "img.jpg" and "date" not in gr.created[0]
        assert gr.updated_places == [] and [e for e in events if e.entity == "place"] == []


class TestPersonMap:
    def test_people_without_the_attribute_map_nothing(self):
        assert sync_immich.person_map([{"handle": "h1", "attribute_list": [{"type": "Nickname", "value": "Ed"}]}]) == {}

    def test_maps_every_immich_person_id_to_its_handle(self):
        people = [linked("abc123", "uuid-1", "uuid-2"), linked("def456", "uuid-3"),
                  {"handle": "ghi789", "attribute_list": [{"type": PERSON_ATTR, "value": "  "}]}]
        assert sync_immich.person_map(people) == {"uuid-1": "abc123", "uuid-2": "abc123", "uuid-3": "def456"}

    def test_loads_from_gramps(self):
        gr = FakeGramps(people={"h-ed": linked("h-ed", "uuid-ed")})
        assert asyncio.run(sync_immich.load_person_map(gr)) == {"uuid-ed": "h-ed"}


class TestPartnerFaces:

    @pytest.fixture
    def conn(self, tmp_path):
        c = db.connect(tmp_path / "t.db")
        yield c
        c.close()

    def _cfg(self, tmp_path):
        return SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="")

    def _gramps(self):
        return FakeGramps(people={"h-ed": linked("h-ed", "uuid-ed")})

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

    def test_tags_union_across_accounts_and_the_owner_keeps_its_own(self, conn):
        base = self._owned("m1", "user-b")
        owner_view = {**base, "tags": [{"value": "Sync/Gramps"}, {"value": "ID/OLDONE"}]}
        other_view = {**base, "tags": [{"value": "Holiday"}]}
        a = FakeImmich(assets={"m1": other_view}, tagged=set(), me_id="user-a")
        b = FakeImmich(assets={"m1": owner_view}, tagged={"m1"}, me_id="user-b")
        merged = asyncio.run(sync_immich._merged_one([a, b], "m1"))
        assert sync_immich.tag_values(merged) == {"sync/gramps", "id/oldone", "holiday"}
        assert sync_immich.owner_tag_values(merged) == {"sync/gramps", "id/oldone"}
        events = self._run(FakeGramps(), [a, b], conn)
        assert actions(events, "would_create")[0].data["cols"] == {"title": "img.jpg"}

    def test_faces_read_via_the_owning_account(self, conn):
        a = FakeImmich(assets={"b1": self._owned("b1", "user-b")},
                       tagged=set(), me_id="user-a")
        b = FakeImmich(assets={"b1": self._owned("b1", "user-b")},
                       tagged={"b1"}, me_id="user-b",
                       faces={"b1": [{"person": {"id": "uuid-ed", "name": "Ed"}}]})
        gr = FakeGramps(people={"h-ed": linked("h-ed", "uuid-ed")})
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
            ("u1", {"ownerId": "unknown", "tags": [{"value": "Holiday"}]}),
            ("u2", {"ownerId": "unknown", "tags": [{"value": "ID/ABC123"}]}),
        ]
        merged = sync_immich._merge_copies(copies)
        assert {t["value"] for t in merged["tags"]} == {"Holiday", "ID/ABC123"}
        assert sync_immich.owner_tag_values(merged) is None

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
        mint(conn, gid, source_id)

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
        owner_view = titled(asset("a1"))
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
        a = titled(asset("a1"))
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
        yield c
        c.close()

    def _cfg(self, tmp_path):
        return SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="")

    def test_face_rect_math(self):
        assert sync_immich._face_rect(self.FACE) == [47, 43, 53, 55]
        assert sync_immich._face_rect({**self.FACE, "imageWidth": 0}) == []
        assert sync_immich._face_rect(
            {**self.FACE, "boundingBoxX2": self.FACE["boundingBoxX1"]}) == []
        near_edge = {"boundingBoxX1": 5, "boundingBoxY1": 5,
                     "boundingBoxX2": 100, "boundingBoxY2": 100,
                     "imageWidth": 100, "imageHeight": 100}
        assert all(0 <= v <= 100 for v in sync_immich._face_rect(near_edge))

    def test_new_link_gets_padded_rect(self, conn, tmp_path):
        im = FakeImmich(assets={"a1": asset("a1")}, tagged={"a1"},
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                       **self.FACE}]})
        gr = FakeGramps(people={"h-ed": linked("h-ed", "uuid-ed")})
        run_scan(im, gr, conn, apply=True, cfg=self._cfg(tmp_path))
        ref = gr.updated_people[0]["media_list"][0]
        assert ref["rect"] == [47, 43, 53, 55]

    def _resume(self, im, gr, conn, cfg):
        async def collect():
            return [e async for e in sync_immich.sync_one_asset(
                gr, [im], conn, cfg, "a1")]
        return asyncio.run(collect())

    def test_empty_rect_healed_on_resync(self, conn, tmp_path):
        mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1")},
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                       **self.FACE}]})
        gr = FakeGramps(
            media={"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                              "desc": "T", "path": "immich/img.jpg"}},
            people={"h-ed": linked("h-ed", "uuid-ed", media_list=[
                {"_class": "MediaRef", "ref": "h1", "rect": []}])})
        events = self._resume(im, gr, conn, self._cfg(tmp_path))
        assert gr.updated_people[0]["media_list"][0]["rect"] == [47, 43, 53, 55]
        assert [e.action for e in events if e.entity == "face"] == ["updated"]

    def test_hand_set_rect_never_touched(self, conn, tmp_path):
        mint(conn, "BBBBBB", "a1")
        im = FakeImmich(assets={"a1": asset("a1")},
                        faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                       **self.FACE}]})
        gr = FakeGramps(
            media={"BBBBBB": {"gramps_id": "BBBBBB", "handle": "h1",
                              "desc": "T", "path": "immich/img.jpg"}},
            people={"h-ed": linked("h-ed", "uuid-ed", media_list=[
                {"_class": "MediaRef", "ref": "h1", "rect": [10, 10, 50, 50]}])})
        events = self._resume(im, gr, conn, self._cfg(tmp_path))
        assert gr.updated_people == []
        assert gr.people["h-ed"]["media_list"][0]["rect"] == [10, 10, 50, 50]
        assert [e.action for e in events if e.entity == "face"] == []
