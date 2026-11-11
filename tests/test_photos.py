import asyncio
import io

import pytest

from bifrost.core import dates
from bifrost.core.clients.immich import ImmichError
from bifrost.core.config import SyncImmichConfig, load_config
from bifrost.modules import codes, photos, sync_immich
from bifrost.modules.sync_immich import SyncError
from test_sync_immich import FakeGramps, FakeImmich, _fresh_register, asset, linked, mint, run_scan, summary_of  # noqa: F401

CFG = SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="ID",
                       gramps_public_url="https://gramps.example")


def tagged(aid, *values, name="img.jpg", desc=None, when="1923-06-15T12:00:00Z"):
    a = asset(aid, name)
    a["tags"] = [{"value": v} for v in values]
    a["localDateTime"] = when
    a["exifInfo"] = {"description": desc} if desc else {}
    return a


def place(gid="P0001", name="Chisago Lake", holding=()):
    return {"handle": f"h-{gid}", "gramps_id": gid, "name": {"value": name},
            "media_list": [sync_immich._media_ref(h) for h in holding], "placeref_list": [], "tag_list": []}


def media(gid="ABC123", handle="h1", desc="T", **extra):
    m = {"gramps_id": gid, "handle": handle, "desc": desc, "path": "immich/img.jpg", "change": 100,
         "attribute_list": [sync_immich._attr("Immich ID", "a1")], "note_list": []}
    m.update(extra)
    return m


def gdate(day, month, year, modifier=0, quality=0, **extra):
    return {"_class": "Date", "dateval": [day, month, year, False], "modifier": modifier,
            "quality": quality, "text": "", **extra}


def note(handle, text, kind="Media Note", gid="N0001"):
    return {"_class": "Note", "handle": handle, "gramps_id": gid, "type": kind,
            "text": {"_class": "StyledText", "string": text, "tags": []}}


def run(coro):
    return asyncio.run(coro)


def load(gr, im, aid, place_rows=None):
    return run(photos.load(gr, [im], CFG, aid, place_rows))


def save(gr, im, aid, form):
    async def collect():
        return [e async for e in photos.save(gr, [im], CFG, aid, form)]
    return run(collect())


def events_of(events, entity):
    return [(e.action, e.data or {}, e.detail) for e in events if e.kind == "item" and e.entity == entity]


class TestDateForms:
    def test_validate_form_fills_precision_from_the_text(self):
        out = photos.validate_form({"title": " T ", "date": {"value": "1923-06"}, "change": "100",
                                    "links": ["https://a.example/x", "https://a.example/x"]})
        assert out["title"] == "T"
        assert out["date"] == {"value": "1923-06-01", "precision": "month",
                               "modifier": "regular", "quality": "regular"}
        assert (out["change"], out["links"], out["gramps_id"]) == (100, ["https://a.example/x"], None)

    def test_validate_form_rejects_bad_values(self):
        with pytest.raises(ValueError, match="unreadable date"):
            photos.validate_form({"date": {"value": "soon"}})
        with pytest.raises(ValueError, match="bad modifier"):
            photos.validate_form({"date": {"value": "1923", "modifier": "circa"}})

    def test_validate_spans_and_decades(self):
        out = photos.validate_form({"date": {"value": "1945", "modifier": "span", "minus": 10, "plus": 5}})
        assert out["date"] == {"value": "1945-01-01", "precision": "year", "modifier": "span",
                               "quality": "regular", "minus": 10, "plus": 5}
        out = photos.validate_form({"date": {"value": "1945-06-15", "modifier": "decade"}})
        assert (out["date"]["precision"], "minus" in out["date"]) == ("year", False)
        for bad in ({"minus": -1}, {"plus": 1000}, {"plus": "5"}):
            with pytest.raises(ValueError, match="bad (minus|plus)"):
                photos.validate_form({"date": {"value": "1945", "modifier": "span", **bad}})

    def test_the_save_body_keeps_the_span_years(self):
        from bifrost.web.routes.photos import PhotoBody
        body = PhotoBody.model_validate(
            {"date": {"value": "1945-01-01", "modifier": "span", "minus": 10, "plus": 5}})
        out = photos.validate_form({"date": dict(body.date)})
        assert (out["date"]["minus"], out["date"]["plus"]) == (10, 5)

    def test_saving_a_new_span_replaces_the_gramps_range(self):
        mint("ABC123", "a1")
        a = tagged("a1", "ID/ABC123", desc="T", when="1945-06-15T12:00:00Z")
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"ABC123": media(date=dates.range_date(1935, 1950, 0))})
        form = {"title": "T", "date": {"value": "1945", "modifier": "span", "minus": 5, "plus": 5}, "change": 100}
        save(gr, im, "a1", form)
        assert gr.updated[0]["date"] == dates.range_date(1940, 1950, 0)
        assert im.upserted == [] and im.untagged_assets == []
        assert load(gr, im, "a1")["date"]["display"] == "Between 1940 and 1950"


class TestDescriptions:
    def test_split_trailing_url(self):
        assert sync_immich.split_description("Easter 1966\nhttps://g/media/ABC123") == (
            "Easter 1966", "https://g/media/ABC123")

    def test_plain_and_multiline_titles(self):
        assert sync_immich.split_description("  Easter 1966 ") == ("Easter 1966", None)
        assert sync_immich.split_description("Line one\nLine two") == ("Line one\nLine two", None)
        assert sync_immich.split_description("") == ("", None)

    def test_the_sync_titles_by_file_name_whatever_the_description_says(self):
        a = tagged("a1", desc="Easter 1966\nhttps://g/media/ABC123")
        assert sync_immich.wanted_title(a) == "img.jpg"

    def test_compose(self):
        assert photos.compose_description("T", None) == "T"
        assert photos.compose_description("T", "https://g/media/X") == "T\nhttps://g/media/X"


class TestSave:
    def _registered(self, **media_extra):
        mint("ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", "ID/ABC123", desc="Old title")
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"ABC123": media(desc="Old title", **media_extra)}, places=[place(), place("P0002", "Taylors Falls")])
        return im, gr

    def test_save_writes_the_gramps_media_and_copies_the_title(self):
        im, gr = self._registered()
        gr.notes["n-other"] = note("n-other", "a researcher's note", kind="Research", gid="N0007")
        gr.media["ABC123"]["note_list"] = ["n-other"]
        gr.media["ABC123"]["attribute_list"].append(sync_immich._attr("Source URL", "https://old.example/x"))
        form = {"title": "Farm, 1923", "notes": "Scanned from the album", "place_gramps_id": "P0001",
                "date": {"value": "1923-06", "modifier": "about", "quality": "estimated"},
                "links": ["https://example.org/box-3", "https://example.org/other"], "change": 100}
        events = save(gr, im, "a1", form)
        saved = gr.media["ABC123"]
        assert saved["desc"] == "Farm, 1923"
        assert saved["date"] == gdate(0, 6, 1923, modifier=3, quality=1)
        assert [(a["type"], a["value"]) for a in saved["attribute_list"]] == [
            ("Immich ID", "a1"), ("Source URL", "https://example.org/box-3"), ("Source URL", "https://example.org/other")]
        new_note = next(n for h, n in gr.notes.items() if h != "n-other")
        assert new_note["type"] == "Media Note" and new_note["text"]["string"] == "Scanned from the album"
        assert saved["note_list"] == ["n-other", new_note["handle"]]
        assert gr.places[0]["media_list"][0]["ref"] == "h1"
        assert im.updated_assets == [("a1", {"description": "Farm, 1923"})]
        assert im.upserted == [] and im.bulk_tagged == []
        summary = summary_of(events).data
        assert summary["created"] is False and summary["warning"] is None
        assert set(summary["changed"]) == {"title", "date", "links"} and summary["note"] == "created"
        assert summary["place"] == "Chisago Lake"
        rec = load(gr, im, "a1", {"P0001": {"name": "Chisago Lake", "hierarchy": ["Chisago Lake", "Minnesota"]}})
        assert (rec["title"], rec["notes"], rec["change"]) == ("Farm, 1923", "Scanned from the album", 101)
        assert rec["date"]["display"] == "Est. About 1923-06" and rec["date_readonly"] is None
        assert [x["url"] for x in rec["links"]] == ["https://example.org/box-3", "https://example.org/other"]
        assert rec["place"] == {"gramps_id": "P0001", "name": "Chisago Lake",
                                "hierarchy": ["Chisago Lake", "Minnesota"], "known": True}

    def test_an_unchanged_save_touches_nothing(self):
        im, gr = self._registered()
        events = save(gr, im, "a1", {"title": "Old title", "change": 100})
        assert gr.updated == [] and im.updated_assets == []
        assert summary_of(events).data["changed"] == {}

    def test_the_first_save_adds_the_photo(self):
        a = tagged("a1", "Date/Year", desc="Immich title")
        im = VersionsImmich(assets={"a1": a})
        gr = FakeGramps(places=[place()])
        form = {"title": "Farm, 1923", "notes": "n", "place_gramps_id": "P0001",
                "date": {"value": "1923", "precision": "year"}, "links": ["https://example.org/x"]}
        events = save(gr, im, "a1", form)
        [created] = gr.created
        gid = created["gramps_id"]
        created = gr.media[gid]
        assert [a["value"] for a in created["attribute_list"] if a["type"] == "Immich ID"] == ["a1"]
        assert (created["desc"], created["date"]) == ("Farm, 1923", gdate(0, 0, 1923))
        assert sync_immich.media_links(created) == ["https://example.org/x"]
        assert gr.places[0]["media_list"][0]["ref"] == created["handle"]
        assert [n["text"]["string"] for n in gr.notes.values()] == ["n"]
        assert im.upserted == [f"ID/{gid}"]
        assert im.metadata["a1"]["bifrost"] == {"gramps_id": gid, "gramps_url": f"https://gramps.example/media/{gid}"}
        assert im.updated_assets == [("a1", {"description": "Farm, 1923"})]
        assert [e.action for e in events if e.entity == "media"][0] == "created"
        assert summary_of(events).data["created"] is True
        rec = load(gr, im, "a1")
        assert rec["gramps"]["gramps_id"] == gid and rec["title"] == "Farm, 1923"

    def test_a_save_with_a_note_or_link_alone_adds_the_photo(self):
        for form in ({"notes": "just a note"}, {"links": ["https://example.org/x"]}, {"place_gramps_id": "P0001"}):
            im = FakeImmich(assets={"a1": tagged("a1")})
            gr = FakeGramps(places=[place()])
            save(gr, im, "a1", form)
            assert len(gr.created) == 1

    def test_a_save_with_nothing_filled_in_adds_nothing(self):
        im = FakeImmich(assets={"a1": tagged("a1", desc="stale")})
        gr = FakeGramps()
        events = save(gr, im, "a1", {"title": ""})
        assert gr.created == []
        assert im.updated_assets == [("a1", {"description": ""})]
        assert summary_of(events).data["gramps_id"] is None

    def test_a_code_written_on_the_photo_is_used(self):
        im = FakeImmich(assets={"a1": tagged("a1")})
        gr = FakeGramps()
        save(gr, im, "a1", {"title": "T", "notes": "Mine", "gramps_id": "rsvd-22"})
        assert gr.created[0]["gramps_id"] == "RSVD22"
        assert [n["text"]["string"] for n in gr.notes.values()] == ["Mine"]
        assert [a["value"] for a in gr.created[0]["attribute_list"] if a["type"] == "Immich ID"] == ["a1"]
        with pytest.raises(SyncError) as exc:
            save(gr, FakeImmich(assets={"a2": tagged("a2")}), "a2", {"title": "T", "gramps_id": "RSVD22"})
        assert exc.value.status == 409 and "already the ID" in exc.value.detail

    def test_the_immich_copy_failing_is_only_a_warning(self):
        im, gr = self._registered()

        async def boom(asset_id, **fields):
            raise ImmichError(500, "immich down")

        im.update_asset = boom
        events = save(gr, im, "a1", {"title": "New", "change": 100})
        assert gr.media["ABC123"]["desc"] == "New"
        assert summary_of(events).data["warning"] == "Immich description not updated: immich down"
        assert [e.action for e in events if e.kind == "item" and e.entity == "media"] == ["updated", "skipped"]

    def test_a_stale_edit_is_refused(self):
        im, gr = self._registered()
        with pytest.raises(SyncError) as exc:
            save(gr, im, "a1", {"title": "New", "change": 99})
        assert exc.value.status == 409 and "reload" in exc.value.detail
        assert gr.updated == [] and im.updated_assets == []
        save(gr, im, "a1", {"title": "New", "change": 100})
        assert gr.media["ABC123"]["desc"] == "New"

    def test_an_unreachable_gramps_saves_nothing(self):
        class DownGramps(FakeGramps):
            async def get_media_by_gramps_id(self, gid, backlinks=False, notes=False):
                raise RuntimeError("connection refused")

        mint("ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", desc="Old")})
        with pytest.raises(SyncError) as exc:
            save(DownGramps({"ABC123": media()}), im, "a1", {"title": "New", "change": 100})
        assert exc.value.status == 502 and im.updated_assets == []
        rec = load(DownGramps({"ABC123": media()}), im, "a1")
        assert rec["gramps_error"].startswith("Gramps could not be read") and rec["title"] == "Old"

    def test_clearing_the_notes_removes_the_media_note(self):
        im, gr = self._registered()
        gr.notes["n-1"] = note("n-1", "old note")
        gr.notes["n-2"] = note("n-2", "second media note", gid="N0002")
        gr.media["ABC123"]["note_list"] = ["n-1", "n-2"]
        save(gr, im, "a1", {"title": "Old title", "notes": "edited", "change": 100})
        assert gr.updated_notes[0]["handle"] == "n-1" and gr.updated_notes[0]["text"]["string"] == "edited"
        assert gr.notes["n-2"]["text"]["string"] == "second media note"
        save(gr, im, "a1", {"title": "Old title", "notes": "", "change": 100})
        assert gr.media["ABC123"]["note_list"] == ["n-2"] and gr.deleted_notes == ["n-1"]

    def test_an_empty_title_falls_back_to_the_file_name(self):
        im, gr = self._registered()
        save(gr, im, "a1", {"title": "", "notes": "n", "change": 100})
        assert gr.media["ABC123"]["desc"] == "img.jpg"

    def test_save_finishes_the_sync_work(self):
        mint("ABC123", "a1")
        a = tagged("a1", desc="T")
        a["originalPath"] = "/up/moved.jpg"
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"ABC123": media()})
        events = save(gr, im, "a1", {"title": "T", "change": 100})
        assert gr.media["ABC123"]["path"] == "immich/moved.jpg"
        assert im.upserted == ["ID/ABC123"]
        cols = [e.data["cols"] for e in events if e.entity == "media" and e.action == "updated"]
        assert set(cols[-1]) == {"file", "id tag"}

    def test_stack_variant_is_refused(self):
        a = tagged("c1")
        a["stack"] = {"id": "s1", "primaryAssetId": "p1"}
        im = FakeImmich(assets={"c1": a})
        with pytest.raises(SyncError, match="stack variant"):
            save(FakeGramps(), im, "c1", {"title": "x"})


class TestPlaces:
    def _registered(self, holding=("h1",), second=()):
        mint("ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "ID/ABC123", desc="T")})
        gr = FakeGramps({"ABC123": media()},
                        places=[place(holding=holding), place("P0002", "Taylors Falls", holding=second)])
        return im, gr

    def test_the_place_is_the_gallery_holding_the_photo(self):
        im, gr = self._registered()
        rec = load(gr, im, "a1")
        assert rec["place"]["gramps_id"] == "P0001" and rec["place"]["name"] == "Chisago Lake"

    def test_changing_the_place_moves_the_photo(self):
        im, gr = self._registered()
        events = save(gr, im, "a1", {"title": "T", "place_gramps_id": "P0002", "change": 100})
        assert gr.places[0]["media_list"] == [] and gr.places[1]["media_list"][0]["ref"] == "h1"
        assert [p["gramps_id"] for p in gr.updated_places] == ["P0001", "P0002"]
        assert events_of(events, "place") == [("updated", {}, "added to the gallery")]
        assert load(gr, im, "a1")["place"]["gramps_id"] == "P0002"
        save(gr, im, "a1", {"title": "T", "place_gramps_id": "P0002", "change": 100})
        assert len(gr.updated_places) == 2

    def test_clearing_the_place_takes_the_photo_out(self):
        im, gr = self._registered()
        save(gr, im, "a1", {"title": "T", "change": 100})
        assert gr.places[0]["media_list"] == []
        assert load(gr, im, "a1")["place"] is None

    def test_an_unknown_place_is_refused_before_anything_is_written(self):
        im, gr = self._registered()
        with pytest.raises(SyncError, match="names no Gramps place"):
            save(gr, im, "a1", {"title": "New", "place_gramps_id": "P0404", "change": 100})
        assert gr.updated == []

    def test_a_photo_in_several_galleries_is_left_alone(self):
        im, gr = self._registered(holding=("h1",), second=("h1",))
        rec = load(gr, im, "a1")
        assert rec["place"] is None and [p["gramps_id"] for p in rec["places"]] == ["P0001", "P0002"]
        save(gr, im, "a1", {"title": "T", "change": 100})
        assert gr.updated_places == []
        assert [len(p["media_list"]) for p in gr.places] == [1, 1]


class TestLoad:
    def test_an_unregistered_photo_opens_with_its_immich_title_and_nothing_else(self):
        a = tagged("a1", "Sync/Gramps", desc="Immich title")
        a["exifInfo"].update({"latitude": 45.5, "longitude": -92.9})
        rec = load(FakeGramps(places=[place()]), FakeImmich(assets={"a1": a}), "a1")
        assert (rec["title"], rec["date"], rec["gramps"], rec["change"]) == ("Immich title", None, None, None)
        assert (rec["place"], rec["places"]) == (None, [])
        assert (rec["notes"], rec["links"], rec["date_readonly"]) == ("", [], None)
        assert rec["immich_date"] == "1923-06-15"

    def test_a_registered_photo_opens_with_what_gramps_has(self):
        mint("ABC123", "a1")
        gr = FakeGramps({"ABC123": media(desc="Gramps title", date=gdate(0, 0, 1923, modifier=1), change=7,
                                         note_list=["n-r", "n-1"],
                                         attribute_list=[sync_immich._attr("Source URL", "https://example.org/x")])})
        gr.notes["n-r"] = note("n-r", "research", kind="Research")
        gr.notes["n-1"] = note("n-1", "the media note")
        rec = load(gr, FakeImmich(assets={"a1": tagged("a1", desc="Immich title")}), "a1")
        assert (rec["title"], rec["date"]["display"], rec["notes"], rec["change"]) == (
            "Gramps title", "Before 1923", "the media note", 7)
        assert [x["url"] for x in rec["links"]] == ["https://example.org/x"]
        assert rec["gramps"] == {"gramps_id": "ABC123", "url": "https://gramps.example/media/ABC123"}

    def test_a_date_the_form_cannot_hold_is_read_only_until_a_new_one_is_entered(self):
        mint("ABC123", "a1")
        textonly = {"_class": "Date", "dateval": [0, 0, 0, False], "modifier": 6, "quality": 0,
                    "text": "the summer Ed left"}
        im = FakeImmich(assets={"a1": tagged("a1", desc="T")})
        gr = FakeGramps({"ABC123": media(date=textonly)})
        rec = load(gr, im, "a1")
        assert (rec["date"], rec["date_readonly"]) == (None, "the summer Ed left")
        save(gr, im, "a1", {"title": "New", "change": 100})
        assert gr.media["ABC123"]["date"] == textonly
        save(gr, im, "a1", {"title": "New", "date": {"value": "1923"}, "change": 101})
        assert gr.media["ABC123"]["date"] == gdate(0, 0, 1923)

    def test_clearing_a_held_date_empties_it(self):
        mint("ABC123", "a1")
        im = VersionsImmich(assets={"a1": tagged("a1", desc="T")})
        gr = FakeGramps({"ABC123": media(date=gdate(0, 0, 1923))})
        save(gr, im, "a1", {"title": "T", "change": 100})
        assert gr.media["ABC123"]["date"] == dates.EMPTY_DATE
        rec = load(gr, im, "a1")
        assert rec["date"] is None and rec["date_readonly"] is None and rec["immich_date"] == "1923-06-15"
        assert im.untagged_assets == []


class TestMergedSpelling:
    def test_merged_copies_keep_tag_spelling(self):
        owner = {"id": "a1", "ownerId": "u1", "tags": [{"value": "ID/ABC123"}, {"value": "Sync/Gramps"}]}
        partner = {"id": "a1", "ownerId": "u1", "tags": [{"value": "Holiday"}]}
        merged = sync_immich._merge_copies([("u1", owner), ("u2", partner)])
        assert [t["value"] for t in merged["tags"]] == ["Holiday", "ID/ABC123", "Sync/Gramps"]


class TestPendingSync:
    def pending(self, im, gr):
        return run(photos.pending_changes(gr, [im], CFG, "a1"))

    def test_in_step_with_gramps(self):
        mint("ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "ID/ABC123", desc="T")})
        assert self.pending(im, FakeGramps({"ABC123": media()})) == []

    def test_title_date_place_and_notes_are_never_pending(self):
        mint("ABC123", "a1")
        a = tagged("a1", "ID/ABC123", desc="Easter 1966")
        a["exifInfo"].update({"latitude": 45.5, "longitude": -92.9})
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"ABC123": media()}, places=[place()])
        assert self.pending(im, gr) == []

    def test_file_and_face_changes_are_pending(self):
        mint("ABC123", "a1")
        a = tagged("a1", "ID/ABC123", desc="T")
        a["originalPath"] = "/up/moved.jpg"
        im = FakeImmich(assets={"a1": a}, faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                                        "boundingBoxX1": 10, "boundingBoxY1": 10,
                                                        "boundingBoxX2": 50, "boundingBoxY2": 50,
                                                        "imageWidth": 100, "imageHeight": 100}]})
        gr = FakeGramps({"ABC123": media()}, people={"h-ed": linked("h-ed", "uuid-ed")})
        assert self.pending(im, gr) == ["faces", "file"]

    def test_a_photo_outside_gramps_has_nothing_pending(self):
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps")})
        assert self.pending(im, FakeGramps()) == []


class TestLinkRecord:
    def test_create_writes_the_record(self):
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps")}, tagged={"a1"})
        gr = FakeGramps()
        run_scan(im, gr, apply=True, cfg=CFG)
        gid = gr.created[0]["gramps_id"]
        assert im.metadata["a1"]["bifrost"] == {"gramps_id": gid,
                                                "gramps_url": f"https://gramps.example/media/{gid}"}

    def test_single_asset_update_copies_the_gramps_title_to_immich(self):
        mint("ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "ID/ABC123", desc="Immich title")})
        gr = FakeGramps({"ABC123": media(desc="Gramps title")})

        async def collect(update):
            return [e async for e in sync_immich.sync_one_asset(
                gr, [im], CFG, "a1", update=update)]

        events = asyncio.run(collect(False))
        assert im.updated_assets == [] and summary_of(events).data["updated"] == {}
        events = asyncio.run(collect(True))
        assert gr.updated == [] and gr.media["ABC123"]["desc"] == "Gramps title"
        assert im.updated_assets == [("a1", {"description": "Gramps title"})]
        assert list(summary_of(events).data["updated"]) == ["description"]
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

    async def upload_asset(self, filename, data, modified_at):
        self.uploads = getattr(self, "uploads", []) + [(filename, data.read(), modified_at)]
        new = tagged("u1", name=filename, when=modified_at)
        new.update({"width": 1000, "height": 800, "ownerId": "me-1", "thumbhash": "th"})
        self.assets["u1"] = new
        return {"id": "u1", "status": "created"}

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
        a = tagged("a1", "Sync/Gramps", "ID/ABC123", desc="Farm")
        a["exifInfo"].update({"latitude": 45.5, "longitude": -92.9})
        b = tagged("b1", "ID/OLDONE", desc="raw scan", when="1924-01-01T12:00:00Z")
        got = photos.drift(photos.version_fields(a, CFG), photos.version_fields(b, CFG))
        assert got == ["location", "tags (missing ID/ABC123, Sync/Gramps; extra ID/OLDONE)"]
        assert photos.drift(photos.version_fields(a, CFG), photos.version_fields(a, CFG)) == []

    def test_title_date_and_their_tags_are_not_compared(self):
        a = tagged("a1", "Sync/Gramps", "Date/Year", "Place/P0001", "Holiday/1923", desc="Farm")
        b = tagged("b1", "Sync/Gramps", "Date/Month", "Family", desc="raw scan", when="1924-01-01T12:00:00Z")
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

    def test_add_version_stacks_and_matches(self):
        a = self._primary()
        n = tagged("n1", "Date/Month", desc="raw scan", when="2020-01-01T12:00:00Z")
        n.update({"width": 1000, "height": 800, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "n1": n}, faces={"a1": [face("p-ed", 100, 100, 300, 300)]})
        im.metadata["a1"] = {"bifrost": {"gramps_id": "ABC123"}}
        rec = run(photos.add_version(FakeGramps(), [im], CFG, "a1", "n1"))
        assert im.created_stacks == [["a1", "n1"]]
        assert im.updated_assets == [("n1", {"latitude": 45.5, "longitude": -92.9})]
        assert n["exifInfo"]["description"] == "raw scan" and n["localDateTime"] == "2020-01-01T12:00:00Z"
        assert len(im.bulk_tagged) == 1 and im.bulk_tagged[0][1] == ["n1"]
        assert im.metadata["n1"]["bifrost"] == {"gramps_id": "ABC123"}
        assert im.faces_created == [("n1", "p-ed", 100, 100, 200, 200)]
        members = rec["versions"]["members"]
        assert [(m["asset_id"], m["is_primary"], m["drift"]) for m in members] == [
            ("a1", True, []), ("n1", False, [])]
        assert sorted(t["value"] for t in n["tags"]) == ["Date/Month", "ID/ABC123", "Sync/Date", "Sync/Gramps"]

    def test_an_upload_joins_as_a_version_with_the_main_tags(self):
        im = VersionsImmich(assets={"a1": self._primary()})
        new_id, rec = run(photos.upload_version(FakeGramps(), [im], CFG, "a1", "rescan.tif",
                                                io.BytesIO(b"tif"), "2026-09-22T10:00:00Z"))
        assert new_id == "u1" and im.uploads == [("rescan.tif", b"tif", "2026-09-22T10:00:00Z")]
        assert im.created_stacks == [["a1", "u1"]]
        assert [(m["asset_id"], m["drift"]) for m in rec["versions"]["members"]] == [("a1", []), ("u1", [])]
        assert "description" not in im.assets["u1"]["exifInfo"]
        assert sorted(t["value"] for t in im.assets["u1"]["tags"]) == ["ID/ABC123", "Sync/Date", "Sync/Gramps"]

    def test_add_version_refuses_stacked_foreign_or_self(self):
        a = self._primary()
        other = tagged("o1")
        other.update({"ownerId": "someone-else"})
        busy = tagged("b1")
        busy.update({"ownerId": "me-1", "stack": {"id": "s9", "primaryAssetId": "b1"}})
        im = VersionsImmich(assets={"a1": a, "o1": other, "b1": busy})
        for target, msg in (("o1", "same Immich account"), ("b1", "already in a stack"), ("a1", "main image")):
            with pytest.raises(SyncError, match=msg):
                run(photos.add_version(FakeGramps(), [im], CFG, "a1", target))
        assert im.created_stacks == []

    def test_drift_is_reported_and_match_fixes_it(self):
        a = self._primary()
        v = tagged("v1", "Sync/Gramps", "Date/Month", desc="old title")
        v.update({"width": 1000, "height": 800, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        rec = load(FakeGramps(), im, "a1")
        assert rec["versions"]["members"][1]["drift"] == ["location", "tags (missing ID/ABC123, Sync/Date)"]
        rec = run(photos.match_member(FakeGramps(), [im], CFG, "a1", "v1"))
        assert rec["versions"]["members"][1]["drift"] == []
        assert im.untagged_assets == [] and v["exifInfo"]["description"] == "old title"

    def test_remove_unstacks_and_strips_identity_tags(self):
        a = self._primary()
        v = tagged("v1", "Sync/Gramps", "ID/ABC123", "Date/Year", "Holiday")
        v.update({"ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        with pytest.raises(SyncError, match="make another version the main image"):
            run(photos.remove_version(FakeGramps(), [im], CFG, "a1", "a1"))
        rec = run(photos.remove_version(FakeGramps(), [im], CFG, "a1", "v1"))
        assert im.removed == [("s1", "v1")]
        assert sorted(t["value"] for t in v["tags"]) == ["Date/Year", "Holiday"]
        assert [m["asset_id"] for m in rec["versions"]["members"]] == ["a1"]

    def test_promote_switches_main_and_the_sync_repoints(self):
        mint("ABC123", "a1")
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
                        people={"h-ed": linked("h-ed", "uuid-ed", media_list=[
                            {"_class": "MediaRef", "ref": "h1", "rect": [10, 10, 30, 30]}])})
        stacked(im, "a1", "v1")
        new_main = run(photos.promote([im], CFG, gr, "a1", "v1", redraw_faces=True))
        assert new_main == "v1"
        assert im.primary_changes == [("s1", "v1")]
        assert im.reassigned == [("uuid-ed", "d1")]
        assert gr.updated_people[0]["media_list"][0]["rect"] == []

        async def collect():
            return [e async for e in sync_immich.sync_one_asset(gr, [im], CFG, "v1", update=True)]

        events = asyncio.run(collect())
        assert gr.updated[0]["path"] == "immich/new.jpg"
        assert [a["value"] for a in gr.media["ABC123"]["attribute_list"] if a["type"] == "Immich ID"] == ["v1"]
        assert gr.updated_people[-1]["media_list"][0]["rect"] == [7, 9, 33, 41]
        assert summary_of(events).data["errors"] == 0

    def test_suggestions_from_duplicates_and_the_id_tag(self):
        mint("ABC123", "a1")
        a = self._primary()
        a["duplicateId"] = "dup-1"
        dup = tagged("d1", desc="same scan")
        dup["duplicateId"] = "dup-1"
        twin = tagged("t1", "ID/ABC123")
        twin["stack"] = {"id": "s9", "primaryAssetId": "t1"}
        im = VersionsImmich(assets={"a1": a, "d1": dup, "t1": twin})
        im.extra_tags["id/abc123"] = {"id": "t-id", "name": "ABC123", "value": "ID/ABC123"}
        im.duplicates = [{"duplicateId": "dup-1", "assets": [a, dup]}]
        rec = load(FakeGramps({"ABC123": media()}), im, "a1")
        assert [(sg["asset_id"], sg["why"], sg["in_stack"]) for sg in rec["suggestions"]] == [
            ("d1", "Immich duplicate", False), ("t1", "tagged ID/ABC123", True)]


class TestRegisterFollowsTheMain:
    def test_sync_of_the_main_repoints_an_immich_id_left_on_a_variant(self):
        mint("ABC123", "v1")
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
            return [e async for e in sync_immich.sync_one_asset(gr, [im], CFG, "a1", update=True)]

        events = asyncio.run(collect())
        assert len(gr.updated) == 1
        assert summary_of(events).data["errors"] == 0
        assert [a["value"] for a in gr.media["ABC123"]["attribute_list"] if a["type"] == "Immich ID"] == ["a1"]


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

    def test_synced_mode_hides_other_accounts_photos(self):
        registered = {"a1": "AAA111", "b1": "BBB222"}
        a = tagged("a1", desc="mine")
        a["ownerId"] = "u-fh"
        b = tagged("b1", desc="theirs")
        b["ownerId"] = "u-me"
        fh = VersionsImmich(assets={"a1": a, "b1": b}, me_id="u-fh")
        fh.label = "fh"
        rows = run(photos.search([fh], registered, mode="synced", browse=[fh]))["items"]
        assert [i["asset_id"] for i in rows] == ["a1", "b1"]
        me = VersionsImmich(assets={"a1": a, "b1": b}, me_id="u-me")
        me.label = "me"
        rows = run(photos.search([fh, me], registered, mode="synced", browse=[fh]))["items"]
        assert [i["asset_id"] for i in rows] == ["a1"]


class TestSearchByCode:
    def _world(self):
        a, b = tagged("a1", desc="Jeb Bush at TurboCam"), tagged("b1", desc="Other")
        return {"a1": "82T4QG", "b1": "BBB222"}, VersionsImmich(assets={"a1": a, "b1": b})

    def test_a_code_brings_up_its_photo_in_either_mode(self):
        registered, im = self._world()
        for mode in ("recent", "synced"):
            r = run(photos.search([im], registered, mode=mode, q=" 82t4qg "))
            assert [(i["asset_id"], i["gramps_id"], i["title"]) for i in r["items"]] == [
                ("a1", "82T4QG", "Jeb Bush at TurboCam")]
            assert r["nextPage"] is None
        assert run(photos.search([im], registered, mode="recent", q="82T4QG", page=2))["items"] == []

    def test_a_code_left_on_a_variant_opens_the_stack_main(self):
        registered, im = self._world()
        v = tagged("v1")
        im.assets["v1"] = v
        stacked(im, "a1", "v1")
        r = run(photos.search([im], {"v1": "82T4QG"}, mode="recent", q="82T4QG"))
        assert [(i["asset_id"], i["gramps_id"]) for i in r["items"]] == [("a1", "82T4QG")]

    def test_an_unknown_code_is_searched_as_text(self):
        registered, im = self._world()
        r = run(photos.search([im], registered, mode="recent", q="ZZZ999"))
        assert [i["asset_id"] for i in r["items"]] == ["a1", "b1"]


class TestVersionLabels:
    def test_the_label_lives_in_the_immich_record_alone(self):
        a = tagged("a1")
        a.update({"ownerId": "me-1"})
        v = tagged("v1")
        v.update({"ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        im.metadata["v1"] = {"bifrost": {"gramps_id": "ABC123"}}
        run(photos.set_version_label([im], "v1", "  screenshot version "))
        assert im.metadata["v1"]["bifrost"] == {"gramps_id": "ABC123", "version_label": "screenshot version"}
        rec = load(FakeGramps(), im, "a1")
        assert [(m["asset_id"], m["label"]) for m in rec["versions"]["members"]] == [("a1", ""), ("v1", "screenshot version")]
        run(photos.set_version_label([im], "a1", "the edited original"))
        assert im.metadata["a1"]["bifrost"] == {"version_label": "the edited original"}
        assert load(FakeGramps(), im, "a1")["label"] == "the edited original"
        run(photos.set_version_label([im], "a1", ""))
        assert im.metadata["a1"] == {}
        assert load(FakeGramps(), im, "a1")["label"] == ""

    def test_match_keeps_the_target_label_and_drops_the_sources(self):
        a = tagged("a1", "Sync/Gramps", desc="T")
        a.update({"width": 100, "height": 80, "ownerId": "me-1"})
        v = tagged("v1", desc="old")
        v.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        im.metadata["a1"] = {"bifrost": {"gramps_id": "ABC123", "version_label": "main scan"}}
        run(photos.set_version_label([im], "v1", "raw"))
        run(photos.match_member(FakeGramps(), [im], CFG, "a1", "v1"))
        assert im.metadata["v1"]["bifrost"] == {"gramps_id": "ABC123", "version_label": "raw"}

    def test_the_sync_record_carries_the_label_and_no_notes(self):
        mint("ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", desc="T")
        im = VersionsImmich(assets={"a1": a})
        run(photos.set_version_label([im], "a1", "edited"))
        save(FakeGramps({"ABC123": media()}), im, "a1", {"title": "T", "notes": "n", "change": 100})
        assert im.metadata["a1"]["bifrost"] == {"gramps_id": "ABC123",
                                                "gramps_url": "https://gramps.example/media/ABC123",
                                                "version_label": "edited"}
        assert sync_immich.link_record("X", CFG, "lbl") == {"gramps_id": "X", "gramps_url": "https://gramps.example/media/X", "version_label": "lbl"}


class TestLinks:
    @pytest.mark.parametrize("url", ["", "example.org/x", "ftp://example.org", "https://a b",
                                     "https://" + "x" * photos.LINK_MAX])
    def test_refusals(self, url):
        with pytest.raises(ValueError):
            photos.validate_form({"links": [url]})

    def test_links_are_source_url_attributes_on_the_media(self):
        mint("ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", "ID/ABC123", desc="T")
        a.update({"width": 100, "height": 80, "ownerId": "me-1"})
        v = tagged("v1")
        v.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        gr = FakeGramps({"ABC123": media()})
        save(gr, im, "a1", {"title": "T", "change": 100,
                                 "links": [" https://example.org/box-3 ", "http://example.org/other"]})
        assert [(x["type"], x["value"]) for x in gr.media["ABC123"]["attribute_list"]] == [
            ("Immich ID", "a1"), ("Source URL", "https://example.org/box-3"), ("Source URL", "http://example.org/other")]
        rec = load(gr, im, "a1")
        assert [x["url"] for x in rec["links"]] == ["https://example.org/box-3", "http://example.org/other"]
        run(photos.promote([im], CFG, gr, "a1", "v1", redraw_faces=False))
        assert [x["url"] for x in load(gr, im, "v1")["links"]] == ["https://example.org/box-3", "http://example.org/other"]
        save(gr, im, "v1", {"title": "T", "change": 101, "links": ["http://example.org/other"]})
        assert sync_immich.media_links(gr.media["ABC123"]) == ["http://example.org/other"]

    def test_api(self):
        from types import SimpleNamespace
        import httpx
        from fastapi import FastAPI
        from bifrost.web.routes import photos as photos_routes
        mint("ABC123", "a1")
        app = FastAPI()
        app.include_router(photos_routes.router)
        app.state.cfg = SimpleNamespace(sync_immich=CFG)
        app.state.immich_accounts = [VersionsImmich(assets={"a1": tagged("a1", "ID/ABC123", desc="T")})]
        app.state.gramps = FakeGramps({"ABC123": media()})
        app.state.caches = {}

        def call(method, url, **kw):
            async def go():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://b") as c:
                    return await c.request(method, url, **kw)
            return asyncio.run(go())

        r = call("GET", "/photos/api/photo/a1")
        assert r.status_code == 200 and r.json()["change"] == 100
        r = call("PUT", "/photos/api/photo/a1", json={"title": "T", "links": ["https://example.org/x"], "change": 100})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["run_id"] and body["summary"]["changed"] == {"links": 1}
        assert [x["url"] for x in body["photo"]["links"]] == ["https://example.org/x"]
        r = call("PUT", "/photos/api/photo/a1", json={"title": "T", "links": ["x"], "change": 101})
        assert r.status_code == 400 and "http" in r.json()["detail"]
        r = call("PUT", "/photos/api/photo/a1", json={"title": "T", "change": 100})
        assert r.status_code == 409 and "reload" in r.json()["detail"]
        assert call("GET", "/photos/api/photo/a1/pending").json() == {"changes": []}


class TestVersionsStayTheirOwn:
    def test_save_leaves_the_versions_title_and_date_alone(self):
        mint("ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", "ID/ABC123", desc="old")
        a.update({"width": 100, "height": 80, "ownerId": "me-1"})
        v = tagged("v1", "Sync/Gramps", desc="raw scan", when="2020-01-01T12:00:00Z")
        v.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        gr = FakeGramps({"ABC123": media(desc="old")})
        save(gr, im, "a1", {"title": "new title", "date": {"value": "1923"}, "change": 100})
        assert gr.media["ABC123"]["desc"] == "new title"
        assert a["exifInfo"]["description"] == "new title"
        assert v["exifInfo"]["description"] == "raw scan" and v["localDateTime"] == "2020-01-01T12:00:00Z"
        assert sorted(t["value"] for t in v["tags"]) == ["ID/ABC123", "Sync/Gramps"]
        rec = load(gr, im, "a1")
        assert rec["versions"]["members"][1]["drift"] == []


class TestSyncedVersionLeads:
    def _pair(self):
        mint("ABC123", "s1")
        unsynced = tagged("u1", "Sync/Gramps", desc="unsynced title")
        unsynced.update({"width": 100, "height": 80, "ownerId": "me-1"})
        synced = tagged("s1", "Sync/Gramps", "Sync/Date", "Date/Year", "ID/ABC123", desc="synced title")
        synced.update({"width": 100, "height": 80, "ownerId": "me-1"})
        return unsynced, synced

    def test_the_gramps_photo_becomes_the_main(self):
        unsynced, synced = self._pair()
        im = VersionsImmich(assets={"u1": unsynced, "s1": synced})
        gr = FakeGramps({"ABC123": media(desc="synced title")})
        rec = run(photos.add_version(gr, [im], CFG, "u1", "s1"))
        assert im.created_stacks == [["s1", "u1"]]
        assert rec["asset_id"] == "s1" and rec["gramps"]["gramps_id"] == "ABC123"
        assert [(m["asset_id"], m["is_primary"], m["drift"]) for m in rec["versions"]["members"]] == [
            ("s1", True, []), ("u1", False, [])]
        assert unsynced["exifInfo"]["description"] == "unsynced title"
        assert sorted(t["value"] for t in unsynced["tags"]) == ["ID/ABC123", "Sync/Date", "Sync/Gramps"]
        assert rec["title"] == "synced title"

    def test_two_gramps_photos_cannot_share_a_stack(self):
        unsynced, synced = self._pair()
        mint("XYZ789", "u1")
        im = VersionsImmich(assets={"u1": unsynced, "s1": synced})
        gr = FakeGramps({"ABC123": media(desc="synced title"), "XYZ789": media(gid="XYZ789", handle="h2")})
        with pytest.raises(SyncError, match="both photos are already in Gramps"):
            run(photos.add_version(gr, [im], CFG, "u1", "s1"))
        assert im.created_stacks == []
