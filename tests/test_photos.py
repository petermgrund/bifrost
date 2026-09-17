import asyncio

import pytest

from bifrost.core import db
from bifrost.core.config import SyncImmichConfig
from bifrost.modules import photos, sync_immich
from bifrost.modules.sync_immich import SyncError
from test_sync_immich import FakeGramps, FakeImmich, actions, asset, mint, run_scan, summary_of

CFG = SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="ID",
                       gramps_public_url="https://gramps.example", place_tag_prefix="Place",
                       note_sync_tag="Sync/Note")


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


def tagged(aid, *values, name="img.jpg", desc=None, when="1923-06-15T12:00:00Z"):
    a = asset(aid, name)
    a["tags"] = [{"value": v} for v in values]
    a["localDateTime"] = when
    a["exifInfo"] = {"description": desc} if desc else {}
    return a


def place(gid="P0001", name="Chisago Lake", coords=False):
    p = {"handle": f"h-{gid}", "gramps_id": gid, "name": {"value": name}, "media_list": [],
         "placeref_list": [], "tag_list": []}
    if coords:
        p.update({"lat": "45.5", "long": "-92.9", "tag_list": ["ptag"]})
    return p


class TestDateForms:
    @pytest.mark.parametrize("text,expected", [
        ("1923", ("1923-01-01", "year")),
        ("1923-6", ("1923-06-01", "month")),
        ("1923-06-15", ("1923-06-15", "exact")),
        (" 1923-06-15 ", ("1923-06-15", "exact")),
    ])
    def test_parse_date_value(self, text, expected):
        assert photos.parse_date_value(text) == expected

    @pytest.mark.parametrize("text", ["", "June 1923", "1923-13", "1923-02-30", "23"])
    def test_unreadable_dates(self, text):
        assert photos.parse_date_value(text) is None

    def test_form_from_tags(self):
        a = tagged("a1", "Sync/Date", "Date/Approximate", "Date/Estimated")
        form = photos.date_form(a)
        assert form == {"value": "1923-06-15", "precision": "month", "modifier": "about",
                        "quality": "estimated", "display": "Est. About 1923-06"}

    def test_year_precision(self):
        form = photos.date_form(tagged("a1", "Date/Year", "Date/Before"))
        assert (form["precision"], form["display"]) == ("year", "Before 1923")

    def test_about_keeps_an_explicit_month_and_matches_the_sync(self):
        a = tagged("a1", "Sync/Date", "Date/Approximate")
        form = photos.date_form(a)
        assert photos.gramps_date(form) == sync_immich.build_gramps_date(a)

    def test_date_tags_round_trip(self):
        form = {"value": "1923-06-15", "precision": "year", "modifier": "after", "quality": "calculated"}
        assert photos.date_tags(form) == {"date/year", "date/after", "date/calculated"}
        assert photos.date_tags({"value": "1923-06-15", "precision": "exact",
                                 "modifier": "regular", "quality": "regular"}) == set()

    def test_validate_form_fills_precision_from_the_text(self):
        out = photos.validate_form({"title": " T ", "date": {"value": "1923-06"}, "sync": {"date": 1}})
        assert out["title"] == "T"
        assert out["date"] == {"value": "1923-06-01", "precision": "month",
                               "modifier": "regular", "quality": "regular"}
        assert out["sync"] == {"media": False, "title": False, "date": True, "note": False}

    def test_validate_form_rejects_bad_values(self):
        with pytest.raises(ValueError, match="unreadable date"):
            photos.validate_form({"date": {"value": "soon"}})
        with pytest.raises(ValueError, match="bad modifier"):
            photos.validate_form({"date": {"value": "1923", "modifier": "circa"}})


class TestDescriptions:
    def test_split_trailing_url(self):
        assert sync_immich.split_description("Easter 1966\nhttps://g/media/ABC123") == (
            "Easter 1966", "https://g/media/ABC123")

    def test_plain_and_multiline_titles(self):
        assert sync_immich.split_description("  Easter 1966 ") == ("Easter 1966", None)
        assert sync_immich.split_description("Line one\nLine two") == ("Line one\nLine two", None)
        assert sync_immich.split_description("") == ("", None)

    def test_sync_title_ignores_the_link_line(self):
        a = tagged("a1", "Sync/Description", desc="Easter 1966\nhttps://g/media/ABC123")
        assert sync_immich.wanted_title(a) == "Easter 1966"

    def test_compose(self):
        assert photos.compose_description("T", None) == "T"
        assert photos.compose_description("T", "https://g/media/X") == "T\nhttps://g/media/X"

    def test_spelling_of_new_tags(self):
        assert photos.spelled("date/month", CFG) == "Date/Month"
        assert photos.spelled("sync/gramps", CFG) == "Sync/Gramps"
        assert photos.spelled("sync/note", CFG) == "Sync/Note"
        assert photos.spelled("Place/P0001", CFG) == "Place/P0001"


def run(coro):
    return asyncio.run(coro)


class TestSave:
    def test_save_writes_fields_tags_notes_and_the_record(self, conn):
        a = tagged("a1", "Sync/Gramps", "Date/Year", "Place/P0009", desc="Old title")
        im = FakeImmich(assets={"a1": a})
        im.extra_tags = {"date/year": {"id": "t-year", "name": "Year", "value": "Date/Year"},
                         "place/p0009": {"id": "t-p9", "name": "P0009", "value": "Place/P0009"}}
        form = {"title": "Farm, 1923", "notes": "Scanned from the album",
                "place_gramps_id": "P0001",
                "date": {"value": "1923-06", "modifier": "about", "quality": "estimated"},
                "sync": {"media": True, "title": True, "date": True, "note": True}}
        rec = run(photos.save([im], conn, CFG, "a1", form, link_on=False,
                              place_rows={"P0001": {"name": "Chisago Lake", "hierarchy": ["Chisago Lake", "Minnesota"]}}))
        assert im.updated_assets == [("a1", {"description": "Farm, 1923",
                                             "dateTimeOriginal": "1923-06-01T12:00:00.000Z"})]
        assert sorted(im.upserted) == ["Date/Approximate", "Date/Estimated", "Date/Month",
                                       "Place/P0001", "Sync/Date", "Sync/Description", "Sync/Note"]
        assert len(im.bulk_tagged) == 1 and im.bulk_tagged[0][1] == ["a1"]
        assert sorted(t for t, _ in im.untagged_assets) == ["t-p9", "t-year"]
        assert im.metadata["a1"]["bifrost"] == {"notes": "Scanned from the album"}
        row = conn.execute("SELECT * FROM photo_notes WHERE asset_id='a1'").fetchone()
        assert row["text"] == "Scanned from the album" and row["gramps_id"] is None
        assert rec["title"] == "Farm, 1923"
        assert rec["date"]["display"] == "Est. About 1923-06"
        assert rec["place"] == {"gramps_id": "P0001", "name": "Chisago Lake",
                                "hierarchy": ["Chisago Lake", "Minnesota"], "tagged": False, "known": True}
        assert rec["sync"] == {"media": True, "title": True, "date": True, "note": True, "location": False}

    def test_link_line_only_with_the_setting_on(self, conn):
        mint(conn, "ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps", desc="T")})
        form = {"title": "T", "sync": {"media": True}}
        run(photos.save([im], conn, CFG, "a1", form, link_on=False))
        assert im.updated_assets == []
        rec = run(photos.save([im], conn, CFG, "a1", form, link_on=True))
        assert im.updated_assets[-1][1]["description"] == "T\nhttps://gramps.example/media/ABC123"
        assert rec["title"] == "T" and rec["link_line"] == "https://gramps.example/media/ABC123"
        assert im.metadata["a1"]["bifrost"] == {"gramps_id": "ABC123",
                                                "gramps_url": "https://gramps.example/media/ABC123"}

    def test_clearing_notes_drops_the_record_and_row(self, conn):
        im = FakeImmich(assets={"a1": tagged("a1")})
        run(photos.save([im], conn, CFG, "a1", {"notes": "x"}, link_on=False))
        assert im.metadata["a1"]["bifrost"] == {"notes": "x"}
        run(photos.save([im], conn, CFG, "a1", {"notes": ""}, link_on=False))
        assert im.metadata["a1"] == {}
        assert conn.execute("SELECT COUNT(*) FROM photo_notes").fetchone()[0] == 0

    def test_stack_variant_is_refused(self, conn):
        a = tagged("c1")
        a["stack"] = {"id": "s1", "primaryAssetId": "p1"}
        im = FakeImmich(assets={"c1": a})
        with pytest.raises(SyncError, match="stack variant"):
            run(photos.save([im], conn, CFG, "c1", {"title": "x"}, link_on=False))


class TestMergedSpelling:
    def test_merged_copies_keep_tag_spelling(self):
        owner = {"id": "a1", "ownerId": "u1", "tags": [{"value": "Place/P0008"}, {"value": "Sync/Gramps"}]}
        partner = {"id": "a1", "ownerId": "u1", "tags": [{"value": "Date/Year"}]}
        merged = sync_immich._merge_copies([("u1", owner), ("u2", partner)])
        assert [t["value"] for t in merged["tags"]] == ["Date/Year", "Place/P0008", "Sync/Gramps"]
        assert sync_immich.place_tag_value(merged, CFG) == "P0008"


class TestPlaceTagSync:
    def test_create_links_the_tagged_place(self, conn):
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps", "Place/P0001")}, tagged={"a1"})
        gr = FakeGramps(places=[place()])
        events = run_scan(im, gr, conn, apply=True, cfg=CFG)
        created = actions(events, "created")
        assert [e.entity for e in created] == ["media", "tag", "place"]
        assert created[2].detail == "media↔place link"
        assert gr.updated_places[0]["media_list"][0]["ref"] == gr.created[0]["handle"]
        assert summary_of(events).data["places_linked"] == 1

    def test_preview_shows_the_place(self, conn):
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps", "Place/P0001")}, tagged={"a1"})
        events = run_scan(im, FakeGramps(places=[place()]), conn, cfg=CFG)
        assert actions(events, "would_create")[0].data["cols"]["place"] == "Chisago Lake"

    def test_tag_beats_gps(self, conn):
        a = tagged("a1", "Sync/Gramps", "Sync/Location", "Place/P0002")
        a["exifInfo"] = {"latitude": 45.5, "longitude": -92.9}
        im = FakeImmich(assets={"a1": a}, tagged={"a1"})
        gr = FakeGramps(places=[place("P0001", "Near by GPS", coords=True), place("P0002", "Tagged")])
        cfg = SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="",
                               place_tag_handle="ptag")
        run_scan(im, gr, conn, apply=True, cfg=cfg)
        assert gr.updated_places[0]["gramps_id"] == "P0002"

    def test_unknown_place_fails_the_place_row_only(self, conn):
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps", "Place/P0404")}, tagged={"a1"})
        gr = FakeGramps(places=[place()])
        events = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert len(gr.created) == 1
        failed = actions(events, "failed")
        assert len(failed) == 1 and failed[0].entity == "place"
        assert "Place/P0404 names no Gramps place" in failed[0].detail

    def test_synced_media_gets_the_place_on_update(self, conn):
        mint(conn, "ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "Place/P0001", "ID/ABC123")})
        media = {"gramps_id": "ABC123", "handle": "h1", "desc": "T", "path": "immich/img.jpg",
                 "attribute_list": [sync_immich._attr("Immich ID", "a1")]}
        gr = FakeGramps({"ABC123": media}, places=[place()])
        events = run_scan(im, gr, conn, cfg=CFG)
        rows = actions(events, "would_update")
        assert [(e.entity, e.data["cols"]) for e in rows] == [("place", {"place": "Chisago Lake"})]
        gr = FakeGramps({"ABC123": dict(media)}, places=[place()])
        events = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert actions(events, "updated")[0].entity == "place"
        assert gr.updated_places[0]["media_list"][0]["ref"] == "h1"


class TestNoteSync:
    def _media(self):
        return {"gramps_id": "ABC123", "handle": "h1", "desc": "T", "path": "immich/img.jpg",
                "attribute_list": [sync_immich._attr("Immich ID", "a1")], "note_list": []}

    def test_note_is_created_then_updated_then_left_alone(self, conn):
        mint(conn, "ABC123", "a1")
        photos.set_note(conn, "a1", "ABC123", "From grandma's album")
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Note", "ID/ABC123")})
        gr = FakeGramps({"ABC123": self._media()})
        preview = run_scan(im, gr, conn, cfg=CFG)
        assert [(e.entity, e.action) for e in preview if e.kind == "item"] == [("note", "would_update")]
        events = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert [(e.entity, e.action) for e in events if e.kind == "item"] == [("note", "created")]
        note = next(iter(gr.notes.values()))
        assert note["type"] == "Media Note" and note["private"] is False
        assert note["text"]["string"] == "From grandma's album"
        assert note["gramps_id"] == "N0001"
        assert gr.updated[-1]["note_list"] == [note["handle"]]
        assert summary_of(events).data["notes_synced"] == 1

        again = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert [e for e in again if e.kind == "item"] == []
        assert summary_of(again).data["skipped"] == 1

        photos.set_note(conn, "a1", "ABC123", "Rewritten")
        events = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert [(e.entity, e.action) for e in events if e.kind == "item"] == [("note", "updated")]
        assert gr.updated_notes[0]["text"]["string"] == "Rewritten"
        assert gr.updated_notes[0]["handle"] == note["handle"]

    def test_no_tag_means_no_gramps_note(self, conn):
        mint(conn, "ABC123", "a1")
        photos.set_note(conn, "a1", "ABC123", "private thoughts")
        im = FakeImmich(assets={"a1": tagged("a1", "ID/ABC123")})
        gr = FakeGramps({"ABC123": self._media()})
        run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert gr.notes == {}

    def test_note_rides_along_on_create(self, conn):
        photos.set_note(conn, "a1", None, "Written before the sync")
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps", "Sync/Note")}, tagged={"a1"})
        gr = FakeGramps()
        events = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert [(e.entity, e.action) for e in events if e.kind == "item" and e.entity != "tag"] == [
            ("media", "created"), ("note", "created")]
        row = conn.execute("SELECT gramps_id, note_handle FROM photo_notes WHERE asset_id='a1'").fetchone()
        assert row["gramps_id"] == gr.created[0]["gramps_id"] and row["note_handle"]
        assert im.metadata["a1"]["bifrost"]["notes"] == "Written before the sync"


class TestLinkRecord:
    def test_create_writes_the_record(self, conn):
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps")}, tagged={"a1"})
        gr = FakeGramps()
        run_scan(im, gr, conn, apply=True, cfg=CFG)
        gid = gr.created[0]["gramps_id"]
        assert im.metadata["a1"]["bifrost"] == {"gramps_id": gid,
                                                "gramps_url": f"https://gramps.example/media/{gid}"}

    def test_single_asset_update_pushes_title_and_reports_it(self, conn):
        mint(conn, "ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Description", "ID/ABC123", desc="New title")})
        media = {"gramps_id": "ABC123", "handle": "h1", "desc": "Old", "path": "immich/img.jpg",
                 "attribute_list": [sync_immich._attr("Immich ID", "a1")]}
        gr = FakeGramps({"ABC123": media})

        async def collect(update):
            return [e async for e in sync_immich.sync_one_asset(
                gr, [im], conn, CFG, "a1", update=update)]

        events = asyncio.run(collect(False))
        assert gr.updated == [] and summary_of(events).data["updated"] == {}
        events = asyncio.run(collect(True))
        assert gr.updated[0]["desc"] == "New title"
        assert list(summary_of(events).data["updated"]) == ["title"]
        assert summary_of(events).data["errors"] == 0


class VersionsImmich(FakeImmich):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.created_stacks = []
        self.primary_changes = []
        self.removed = []
        self.faces_created = []
        self.reassigned = []
        self.duplicates = []

    async def create_stack(self, asset_ids):
        members = list(dict.fromkeys(asset_ids))
        self.created_stacks.append(members)
        sid = f"s{len(self.created_stacks)}"
        self.stacks = [s for s in self.stacks
                       if not {a["id"] for a in s["assets"]} & set(members)]
        stack = {"id": sid, "primaryAssetId": members[0], "assets": [self.assets[a] for a in members]}
        self.stacks.append(stack)
        for a in members:
            self.assets[a]["stack"] = {"id": sid, "primaryAssetId": members[0], "assetCount": len(members)}
        return stack

    async def update_stack(self, stack_id, primary_asset_id):
        self.primary_changes.append((stack_id, primary_asset_id))
        for s in self.stacks:
            if s["id"] == stack_id:
                s["primaryAssetId"] = primary_asset_id
                for a in s["assets"]:
                    a["stack"]["primaryAssetId"] = primary_asset_id
                return s
        raise ImmichError(400, "no such stack")

    async def remove_stack_asset(self, stack_id, asset_id):
        self.removed.append((stack_id, asset_id))
        for s in self.stacks:
            if s["id"] == stack_id:
                s["assets"] = [a for a in s["assets"] if a["id"] != asset_id]
        self.assets[asset_id].pop("stack", None)

    async def create_face(self, asset_id, person_id, image_width, image_height, x, y, width, height):
        self.faces_created.append((asset_id, person_id, x, y, width, height))
        self.faces.setdefault(asset_id, []).append({
            "id": f"f{len(self.faces_created)}", "person": {"id": person_id},
            "boundingBoxX1": x, "boundingBoxY1": y, "boundingBoxX2": x + width, "boundingBoxY2": y + height,
            "imageWidth": image_width, "imageHeight": image_height})

    async def reassign_face(self, person_id, face_id):
        self.reassigned.append((person_id, face_id))

    async def list_duplicates(self):
        return self.duplicates

    async def search_assets(self, page=1, size=60, person_id=None, filename=None, order="desc",
                            tag_id=None, description=None, order_by=None, album_id=None):
        if album_id:
            album = next((a for a in getattr(self, "albums", []) if a["id"] == album_id), None)
            items = [self.assets[i] for i in (album or {}).get("asset_ids", []) if i in self.assets]
            if order == "asc":
                items = list(reversed(items))
            return {"items": items, "nextPage": None}
        value = self._tag_value(tag_id) if tag_id else None
        items = [a for a in self.assets.values() if value and any(
            (t.get("value") or "").lower() == value.lower() for t in a.get("tags") or [])]
        if not tag_id:
            items = [a for a in self.assets.values() if not a.get("stack") or a["stack"].get("primaryAssetId") == a["id"]]
        return {"items": items, "nextPage": None}

    async def list_albums(self):
        return [{"id": a["id"], "albumName": a["name"], "assetCount": len(a["asset_ids"]),
                 "description": a.get("description", ""), "order": a.get("order", "desc"),
                 "albumThumbnailAssetId": a["asset_ids"][0] if a["asset_ids"] else None}
                for a in getattr(self, "albums", [])]


def stacked(im, primary, *others):
    return asyncio.run(im.create_stack([primary, *others]))


def face(pid, x1, y1, x2, y2, w=1000, h=800, fid="f-src", name="Ed"):
    return {"id": fid, "person": {"id": pid, "name": name} if pid else None,
            "boundingBoxX1": x1, "boundingBoxY1": y1, "boundingBoxX2": x2, "boundingBoxY2": y2,
            "imageWidth": w, "imageHeight": h}


class TestVersionFields:
    def test_drift_lists_what_differs(self):
        a = tagged("a1", "Sync/Gramps", "Date/Year", "ID/ABC123", "Place/P0001", desc="Farm")
        a["exifInfo"].update({"latitude": 45.5, "longitude": -92.9})
        b = tagged("b1", "Sync/Gramps", "Date/Month", "ID/ABC123", desc="raw scan", when="1924-01-01T12:00:00Z")
        got = photos.drift(photos.version_fields(a, CFG), photos.version_fields(b, CFG))
        assert got == ["title", "date", "location",
                       "tags (missing Date/Year, Place/P0001; extra Date/Month)"]
        assert photos.drift(photos.version_fields(a, CFG), photos.version_fields(a, CFG)) == []

    def test_unmanaged_tags_are_ignored(self):
        a = tagged("a1", "Sync/Gramps", "Holiday/1923")
        b = tagged("b1", "Sync/Gramps", "Family")
        assert photos.drift(photos.version_fields(a, CFG), photos.version_fields(b, CFG)) == []


class TestCopyFaces:
    def test_overlapping_face_is_reassigned_else_created(self):
        src = tagged("a1")
        src.update({"width": 1000, "height": 800})
        dst = tagged("b1")
        dst.update({"width": 2000, "height": 1600})
        im = VersionsImmich(assets={"a1": src, "b1": dst}, faces={
            "a1": [face("p-ed", 100, 100, 300, 300, fid="s1"), face("p-ann", 600, 100, 800, 300, fid="s2", name="Ann")],
            "b1": [face(None, 220, 180, 620, 620, w=2000, h=1600, fid="d1")]})
        copied = run(photos.copy_faces(im, src, dst))
        assert copied == 2
        assert im.reassigned == [("p-ed", "d1")]
        assert im.faces_created == [("b1", "p-ann", 1200, 200, 400, 400)]

    def test_already_present_person_is_left_alone(self):
        src = tagged("a1")
        dst = tagged("b1")
        dst.update({"width": 1000, "height": 800})
        im = VersionsImmich(assets={"a1": src, "b1": dst}, faces={
            "a1": [face("p-ed", 100, 100, 300, 300)], "b1": [face("p-ed", 500, 500, 700, 700, fid="d1")]})
        assert run(photos.copy_faces(im, src, dst)) == 0
        assert im.reassigned == [] and im.faces_created == []


class TestVersions:
    def _primary(self):
        a = tagged("a1", "Sync/Gramps", "Sync/Date", "Date/Year", "ID/ABC123", "Place/P0001", "Holiday",
                   desc="The farm, 1923")
        a["exifInfo"].update({"latitude": 45.5, "longitude": -92.9})
        a.update({"width": 1000, "height": 800, "ownerId": "me-1"})
        return a

    def test_add_version_stacks_and_matches(self, conn):
        a = self._primary()
        n = tagged("n1", "Date/Month", desc="raw scan", when="2020-01-01T12:00:00Z")
        n.update({"width": 1000, "height": 800, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "n1": n}, faces={"a1": [face("p-ed", 100, 100, 300, 300)]})
        im.metadata["a1"] = {"bifrost": {"gramps_id": "ABC123", "notes": "n"}}
        rec = run(photos.add_version([im], conn, CFG, "a1", "n1"))
        assert im.created_stacks == [["a1", "n1"]]
        assert im.updated_assets == [("n1", {"description": "The farm, 1923",
                                             "dateTimeOriginal": "1923-06-15T12:00:00.000Z",
                                             "latitude": 45.5, "longitude": -92.9})]
        assert len(im.bulk_tagged) == 1 and im.bulk_tagged[0][1] == ["n1"]
        assert im.metadata["n1"]["bifrost"] == {"gramps_id": "ABC123", "notes": "n"}
        assert im.faces_created == [("n1", "p-ed", 100, 100, 200, 200)]
        members = rec["versions"]["members"]
        assert [(m["asset_id"], m["is_primary"], m["drift"]) for m in members] == [
            ("a1", True, []), ("n1", False, [])]
        assert sorted(t["value"] for t in n["tags"]) == [
            "Date/Year", "ID/ABC123", "Place/P0001", "Sync/Date", "Sync/Gramps"]

    def test_add_version_refuses_stacked_foreign_or_self(self, conn):
        a = self._primary()
        other = tagged("o1")
        other.update({"ownerId": "someone-else"})
        busy = tagged("b1")
        busy.update({"ownerId": "me-1", "stack": {"id": "s9", "primaryAssetId": "b1"}})
        im = VersionsImmich(assets={"a1": a, "o1": other, "b1": busy})
        for target, msg in (("o1", "same Immich account"), ("b1", "already in a stack"), ("a1", "main image")):
            with pytest.raises(SyncError, match=msg):
                run(photos.add_version([im], conn, CFG, "a1", target))
        assert im.created_stacks == []

    def test_drift_is_reported_and_match_fixes_it(self, conn):
        a = self._primary()
        v = tagged("v1", "Sync/Gramps", "Date/Month", desc="old title")
        v.update({"width": 1000, "height": 800, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        rec = run(photos.load([im], conn, CFG, "a1"))
        assert rec["versions"]["members"][1]["drift"] == [
            "title", "location", "tags (missing Date/Year, ID/ABC123, Place/P0001, Sync/Date; extra Date/Month)"]
        rec = run(photos.match_member([im], conn, CFG, "a1", "v1"))
        assert rec["versions"]["members"][1]["drift"] == []
        assert [t for t, _ in im.untagged_assets] == [im.extra_tags["date/month"]["id"]]

    def test_remove_unstacks_and_strips_identity_tags(self, conn):
        a = self._primary()
        v = tagged("v1", "Sync/Gramps", "ID/ABC123", "Date/Year", "Holiday")
        v.update({"ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        with pytest.raises(SyncError, match="make another version the main image"):
            run(photos.remove_version([im], conn, CFG, "a1", "a1"))
        rec = run(photos.remove_version([im], conn, CFG, "a1", "v1"))
        assert im.removed == [("s1", "v1")]
        assert sorted(t["value"] for t in v["tags"]) == ["Date/Year", "Holiday"]
        assert [m["asset_id"] for m in rec["versions"]["members"]] == ["a1"]

    def test_promote_switches_main_moves_notes_and_the_sync_repoints(self, conn):
        mint(conn, "ABC123", "a1")
        photos.set_note(conn, "a1", "ABC123", "kept")
        a = self._primary()
        a["originalPath"] = "/up/old.jpg"
        v = tagged("v1", desc="better scan", name="new.jpg")
        v.update({"width": 2000, "height": 1600, "ownerId": "me-1", "originalPath": "/up/new.jpg"})
        im = VersionsImmich(assets={"a1": a, "v1": v},
                            faces={"a1": [face("uuid-ed", 100, 100, 300, 300)],
                                   "v1": [face(None, 200, 200, 600, 600, w=2000, h=1600, fid="d1")]})
        media = {"gramps_id": "ABC123", "handle": "h1", "desc": "The farm, 1923", "path": "immich/old.jpg",
                 "mime": "image/jpeg", "attribute_list": [sync_immich._attr("Immich ID", "a1")]}
        gr = FakeGramps({"ABC123": media}, places=[place()],
                        people={"h-ed": {"handle": "h-ed", "media_list": [
                            {"_class": "MediaRef", "ref": "h1", "rect": [10, 10, 30, 30]}]}})
        conn.execute("INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
                     "VALUES ('h-ed', 'uuid-ed', 'Ed', 't')")
        conn.commit()
        stacked(im, "a1", "v1")
        new_main = run(photos.promote([im], conn, CFG, gr, "a1", "v1", redraw_faces=True))
        assert new_main == "v1"
        assert im.primary_changes == [("s1", "v1")]
        assert im.reassigned == [("uuid-ed", "d1")]
        row = conn.execute("SELECT asset_id, text FROM photo_notes").fetchone()
        assert (row["asset_id"], row["text"]) == ("v1", "kept")
        assert gr.updated_people[0]["media_list"][0]["rect"] == []

        async def collect():
            return [e async for e in sync_immich.sync_one_asset(gr, [im], conn, CFG, "v1", update=True)]

        events = asyncio.run(collect())
        assert gr.updated[0]["path"] == "immich/new.jpg"
        assert conn.execute("SELECT source_id FROM minted_media WHERE gramps_id='ABC123'").fetchone()[0] == "v1"
        assert gr.updated_people[-1]["media_list"][0]["rect"] == [7, 9, 33, 41]
        assert summary_of(events).data["errors"] == 0

    def test_suggestions_from_duplicates_and_the_id_tag(self, conn):
        mint(conn, "ABC123", "a1")
        a = self._primary()
        a["duplicateId"] = "dup-1"
        dup = tagged("d1", desc="same scan")
        dup["duplicateId"] = "dup-1"
        twin = tagged("t1", "ID/ABC123")
        twin["stack"] = {"id": "s9", "primaryAssetId": "t1"}
        im = VersionsImmich(assets={"a1": a, "d1": dup, "t1": twin})
        im.extra_tags["id/abc123"] = {"id": "t-id", "name": "ABC123", "value": "ID/ABC123"}
        im.duplicates = [{"duplicateId": "dup-1", "assets": [a, dup]}]
        rec = run(photos.load([im], conn, CFG, "a1"))
        assert [(sg["asset_id"], sg["why"], sg["in_stack"]) for sg in rec["suggestions"]] == [
            ("d1", "Immich duplicate", False), ("t1", "tagged ID/ABC123", True)]


class TestRegisterFollowsTheMain:
    def test_sync_of_the_main_repoints_a_register_row_left_on_a_variant(self, conn):
        mint(conn, "ABC123", "v1")
        a = tagged("a1", "ID/ABC123")
        a["stack"] = {"id": "s1", "primaryAssetId": "a1"}
        v = tagged("v1")
        v["stack"] = {"id": "s1", "primaryAssetId": "a1"}
        im = VersionsImmich(assets={"a1": a, "v1": v},
                            stacks=[{"id": "s1", "primaryAssetId": "a1", "assets": [a, v]}])
        media = {"gramps_id": "ABC123", "handle": "h1", "desc": "T", "path": "immich/img.jpg",
                 "attribute_list": [sync_immich._attr("Immich ID", "a1")]}
        gr = FakeGramps({"ABC123": media})

        async def collect():
            return [e async for e in sync_immich.sync_one_asset(gr, [im], conn, CFG, "a1", update=True)]

        events = asyncio.run(collect())
        assert gr.updated == []
        assert summary_of(events).data["errors"] == 0
        assert conn.execute("SELECT source_id FROM minted_media WHERE gramps_id='ABC123'").fetchone()[0] == "a1"


from bifrost.modules import photo_collections as pc  # noqa: E402


class TestCollections:
    def test_crud_and_listing(self, conn):
        c = pc.create(conn, "  Farm album ", "the Lindqvist farm over the years")
        assert (c["name"], c["description"]) == ("Farm album", "the Lindqvist farm over the years")
        with pytest.raises(ValueError):
            pc.create(conn, "   ")
        pc.update(conn, c["id"], "Farm", "")
        assert pc.get(conn, c["id"])["name"] == "Farm"
        assert [x["name"] for x in pc.list_all(conn)] == ["Farm"]
        assert pc.list_all(conn)[0]["count"] == 0 and pc.list_all(conn)[0]["cover"] is None
        assert pc.delete(conn, c["id"]) is True
        assert pc.get(conn, c["id"]) is None and pc.delete(conn, c["id"]) is False

    def test_items_keep_insertion_order_and_dedupe(self, conn):
        c = pc.create(conn, "Farm")
        assert pc.add_items(conn, c["id"], ["a1", "b1", "a1", ""]) == 2
        assert pc.add_items(conn, c["id"], ["b1", "c1"]) == 1
        assert pc.item_ids(conn, c["id"]) == ["a1", "b1", "c1"]
        listed = pc.list_all(conn)[0]
        assert (listed["count"], listed["cover"]) == (3, "a1")
        assert pc.remove_item(conn, c["id"], "b1") is True
        assert pc.item_ids(conn, c["id"]) == ["a1", "c1"]
        assert pc.for_asset(conn, "a1") == [{"id": c["id"], "name": "Farm"}]
        assert pc.for_asset(conn, "b1") == []

    def test_reorder_is_total_and_tolerant(self, conn):
        c = pc.create(conn, "Farm")
        pc.add_items(conn, c["id"], ["a1", "b1", "c1", "d1"])
        assert pc.reorder(conn, c["id"], ["c1", "a1", "zz"]) == ["c1", "a1", "b1", "d1"]
        assert pc.item_ids(conn, c["id"]) == ["c1", "a1", "b1", "d1"]
        pc.add_items(conn, c["id"], ["e1"])
        assert pc.item_ids(conn, c["id"]) == ["c1", "a1", "b1", "d1", "e1"]

    def test_cap(self, conn):
        c = pc.create(conn, "Big")
        pc.add_items(conn, c["id"], [f"a{i}" for i in range(pc.MAX_ITEMS)])
        with pytest.raises(ValueError, match="at most"):
            pc.add_items(conn, c["id"], ["one-more"])

    def test_deleting_a_collection_drops_its_items(self, conn):
        c = pc.create(conn, "Farm")
        pc.add_items(conn, c["id"], ["a1"])
        pc.delete(conn, c["id"])
        assert conn.execute("SELECT COUNT(*) FROM collection_items").fetchone()[0] == 0

    def test_memberships_follow_the_main_image(self, conn):
        one = pc.create(conn, "One")
        two = pc.create(conn, "Two")
        pc.add_items(conn, one["id"], ["old", "x"])
        pc.add_items(conn, two["id"], ["new", "old"])
        assert pc.move_items(conn, "old", "new") == 2
        assert pc.item_ids(conn, one["id"]) == ["new", "x"]
        assert pc.item_ids(conn, two["id"]) == ["new"]

    def test_cards_for_marks_missing_assets_and_keeps_order(self, conn):
        mint(conn, "ABC123", "a1")
        im = VersionsImmich(assets={"a1": tagged("a1", desc="Farm"), "b1": tagged("b1", name="b.jpg")})
        cards = run(photos.cards_for([im], conn, ["b1", "gone", "a1"]))
        assert [(c["asset_id"], c["title"] or c["filename"], c["gramps_id"], c["missing"]) for c in cards] == [
            ("b1", "b.jpg", None, False), ("gone", "", None, True), ("a1", "Farm", "ABC123", False)]

    def test_primaries_of_swaps_variants_for_their_main(self, conn):
        a, v = tagged("a1"), tagged("v1")
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        assert run(photos.primaries_of([im], ["v1", "z1", "a1"])) == ["a1", "z1"]

    def test_promote_moves_memberships(self, conn):
        c = pc.create(conn, "Farm")
        pc.add_items(conn, c["id"], ["a1"])
        a = tagged("a1", "Sync/Gramps")
        a.update({"width": 100, "height": 80, "ownerId": "me-1"})
        v = tagged("v1")
        v.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        run(photos.promote([im], conn, CFG, FakeGramps(), "a1", "v1", redraw_faces=False))
        assert pc.item_ids(conn, c["id"]) == ["v1"]
        rec = run(photos.load([im], conn, CFG, "v1"))
        assert rec["collections"] == [{"id": c["id"], "name": "Farm"}]


from bifrost.core.config import load_config  # noqa: E402


class TestBrowseAccounts:
    def test_config_accepts_a_list_or_a_string(self, tmp_path):
        base = "gramps: {base_url: x, username: u, password: p}\npaperless: {base_url: x, api_token: t}\n"
        (tmp_path / "a.yaml").write_text(base + "sync:\n  immich:\n    photos_accounts: [fh, ' ']\n")
        (tmp_path / "b.yaml").write_text(base + "sync:\n  immich:\n    photos_accounts: fh\n")
        (tmp_path / "c.yaml").write_text(base)
        assert load_config(tmp_path / "a.yaml").sync_immich.photos_accounts == ("fh",)
        assert load_config(tmp_path / "b.yaml").sync_immich.photos_accounts == ("fh",)
        assert load_config(tmp_path / "c.yaml").sync_immich.photos_accounts == ()

    def test_filter_by_label(self):
        fh, me = FakeImmich(me_id="u-fh"), FakeImmich(me_id="u-me")
        fh.label, me.label = "fh", "me"
        assert photos.browse_accounts([fh, me], CFG) == [fh, me]
        cfg = SyncImmichConfig(photos_accounts=("FH",))
        assert photos.browse_accounts([fh, me], cfg) == [fh]
        with pytest.raises(SyncError, match="names no configured Immich account"):
            photos.browse_accounts([fh, me], SyncImmichConfig(photos_accounts=("nobody",)))

    def test_synced_mode_hides_other_accounts_photos(self, conn):
        mint(conn, "AAA111", "a1")
        mint(conn, "BBB222", "b1")
        a = tagged("a1", desc="mine")
        a["ownerId"] = "u-fh"
        b = tagged("b1", desc="theirs")
        b["ownerId"] = "u-me"
        fh = VersionsImmich(assets={"a1": a, "b1": b}, me_id="u-fh")
        fh.label = "fh"
        rows = run(photos.search([fh], conn, CFG, mode="synced", browse=[fh]))["items"]
        assert [i["asset_id"] for i in rows] == ["a1", "b1"]
        me = VersionsImmich(assets={"a1": a, "b1": b}, me_id="u-me")
        me.label = "me"
        rows = run(photos.search([fh, me], conn, CFG, mode="synced", browse=[fh]))["items"]
        assert [i["asset_id"] for i in rows] == ["a1"]


class TestVersionLabels:
    def test_label_is_kept_in_bifrost_and_the_immich_record(self, conn):
        a = tagged("a1")
        a.update({"ownerId": "me-1"})
        v = tagged("v1")
        v.update({"ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        im.metadata["v1"] = {"bifrost": {"gramps_id": "ABC123"}}
        run(photos.set_version_label([im], conn, CFG, "v1", "  screenshot version "))
        assert im.metadata["v1"]["bifrost"] == {"gramps_id": "ABC123", "version_label": "screenshot version"}
        rec = run(photos.load([im], conn, CFG, "a1"))
        assert [(m["asset_id"], m["label"]) for m in rec["versions"]["members"]] == [("a1", ""), ("v1", "screenshot version")]
        run(photos.set_version_label([im], conn, CFG, "a1", "the edited original"))
        assert im.metadata["a1"]["bifrost"] == {"version_label": "the edited original"}
        assert run(photos.load([im], conn, CFG, "a1"))["label"] == "the edited original"
        run(photos.set_version_label([im], conn, CFG, "a1", ""))
        assert im.metadata["a1"] == {}
        assert conn.execute("SELECT COUNT(*) FROM version_labels").fetchone()[0] == 1

    def test_match_keeps_the_target_label_and_drops_the_sources(self, conn):
        a = tagged("a1", "Sync/Gramps", desc="T")
        a.update({"width": 100, "height": 80, "ownerId": "me-1"})
        v = tagged("v1", desc="old")
        v.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        im.metadata["a1"] = {"bifrost": {"gramps_id": "ABC123", "notes": "n", "version_label": "main scan"}}
        run(photos.set_version_label([im], conn, CFG, "v1", "raw"))
        run(photos.match_member([im], conn, CFG, "a1", "v1"))
        assert im.metadata["v1"]["bifrost"] == {"gramps_id": "ABC123", "notes": "n", "version_label": "raw"}

    def test_save_and_sync_records_carry_the_label(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", "ID/ABC123", desc="T")
        im = VersionsImmich(assets={"a1": a})
        run(photos.set_version_label([im], conn, CFG, "a1", "edited"))
        run(photos.save([im], conn, CFG, "a1", {"title": "T", "notes": "n", "sync": {"media": True}}, link_on=False))
        assert im.metadata["a1"]["bifrost"] == {"gramps_id": "ABC123",
                                                "gramps_url": "https://gramps.example/media/ABC123",
                                                "notes": "n", "version_label": "edited"}
        assert sync_immich.link_record("X", CFG, "", "lbl") == {"gramps_id": "X", "gramps_url": "https://gramps.example/media/X", "version_label": "lbl"}


class TestAlbumImport:
    def test_import_makes_an_ordered_collection_of_main_images(self, conn):
        a, v, b, c = tagged("a1", desc="A"), tagged("v1"), tagged("b1", desc="B"), tagged("c1", desc="C")
        im = VersionsImmich(assets={"a1": a, "v1": v, "b1": b, "c1": c})
        im.label = "fh"
        stacked(im, "a1", "v1")
        im.albums = [{"id": "al-1", "name": "Summer 1923", "description": "the farm", "order": "asc",
                      "asset_ids": ["c1", "v1", "b1"]}]
        albums = run(photos.list_albums([im]))
        assert albums == [{"id": "al-1", "name": "Summer 1923", "count": 3, "description": "the farm",
                           "order": "asc", "account": "fh", "thumb": "/photos/api/thumb/c1"}]
        cid, added = run(photos.import_album([im], [im], conn, "al-1"))
        assert added == 3
        assert pc.get(conn, cid)["name"] == "Summer 1923"
        assert pc.get(conn, cid)["description"] == "the farm"
        assert pc.item_ids(conn, cid) == ["b1", "a1", "c1"]
        with pytest.raises(SyncError, match="no such Immich album"):
            run(photos.import_album([im], [im], conn, "al-9"))
