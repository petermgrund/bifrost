import asyncio
import io

import pytest

from bifrost.core import dates, db
from bifrost.core import settings as ui_settings
from bifrost.core.clients.immich import ImmichError
from bifrost.core.config import SyncImmichConfig
from bifrost.modules import codes, photos, sync_immich
from bifrost.modules.sync_immich import SyncError
from test_sync_immich import FakeGramps, FakeImmich, asset, linked, mint, run_scan, summary_of

CFG = SyncImmichConfig(path_mappings=(("/up/", "immich/"),), id_tag_prefix="ID",
                       gramps_public_url="https://gramps.example")


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


def load(gr, im, conn, aid, place_rows=None):
    return run(photos.load(gr, [im], conn, CFG, aid, place_rows))


def save(gr, im, conn, aid, form):
    async def collect():
        return [e async for e in photos.save(gr, [im], conn, CFG, aid, form)]
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

    def test_saving_a_new_span_replaces_the_gramps_range(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "ID/ABC123", desc="T", when="1945-06-15T12:00:00Z")
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"ABC123": media(date=dates.range_date(1935, 1950, 0))})
        form = {"title": "T", "date": {"value": "1945", "modifier": "span", "minus": 5, "plus": 5}, "change": 100}
        save(gr, im, conn, "a1", form)
        assert gr.updated[0]["date"] == dates.range_date(1940, 1950, 0)
        assert im.upserted == [] and im.untagged_assets == []
        assert load(gr, im, conn, "a1")["date"]["display"] == "Between 1940 and 1950"


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
    def _registered(self, conn, **media_extra):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", "ID/ABC123", desc="Old title")
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"ABC123": media(desc="Old title", **media_extra)}, places=[place(), place("P0002", "Taylors Falls")])
        return im, gr

    def test_save_writes_the_gramps_media_and_copies_the_title(self, conn):
        im, gr = self._registered(conn)
        gr.notes["n-other"] = note("n-other", "a researcher's note", kind="Research", gid="N0007")
        gr.media["ABC123"]["note_list"] = ["n-other"]
        gr.media["ABC123"]["attribute_list"].append(sync_immich._attr("Source URL", "https://old.example/x"))
        form = {"title": "Farm, 1923", "notes": "Scanned from the album", "place_gramps_id": "P0001",
                "date": {"value": "1923-06", "modifier": "about", "quality": "estimated"},
                "links": ["https://example.org/box-3", "https://example.org/other"], "change": 100}
        ui_settings.set_description_link(conn, True)
        events = save(gr, im, conn, "a1", form)
        saved = gr.media["ABC123"]
        assert saved["desc"] == "Farm, 1923"
        assert saved["date"] == gdate(0, 6, 1923, modifier=3, quality=1)
        assert [(a["type"], a["value"]) for a in saved["attribute_list"]] == [
            ("Immich ID", "a1"), ("Source URL", "https://example.org/box-3"), ("Source URL", "https://example.org/other")]
        new_note = next(n for h, n in gr.notes.items() if h != "n-other")
        assert new_note["type"] == "Media Note" and new_note["text"]["string"] == "Scanned from the album"
        assert saved["note_list"] == ["n-other", new_note["handle"]]
        assert gr.places[0]["media_list"][0]["ref"] == "h1"
        assert im.updated_assets == [("a1", {"description": "Farm, 1923\nhttps://gramps.example/media/ABC123"})]
        assert im.upserted == [] and im.bulk_tagged == []
        summary = summary_of(events).data
        assert summary["created"] is False and summary["warning"] is None
        assert set(summary["changed"]) == {"title", "date", "links"} and summary["note"] == "created"
        assert summary["place"] == "Chisago Lake"
        rec = load(gr, im, conn, "a1", {"P0001": {"name": "Chisago Lake", "hierarchy": ["Chisago Lake", "Minnesota"]}})
        assert (rec["title"], rec["notes"], rec["change"]) == ("Farm, 1923", "Scanned from the album", 101)
        assert rec["date"]["display"] == "Est. About 1923-06" and rec["date_readonly"] is None
        assert [x["url"] for x in rec["links"]] == ["https://example.org/box-3", "https://example.org/other"]
        assert rec["place"] == {"gramps_id": "P0001", "name": "Chisago Lake",
                                "hierarchy": ["Chisago Lake", "Minnesota"], "known": True}

    def test_an_unchanged_save_touches_nothing(self, conn):
        im, gr = self._registered(conn)
        events = save(gr, im, conn, "a1", {"title": "Old title", "change": 100})
        assert gr.updated == [] and im.updated_assets == []
        assert summary_of(events).data["changed"] == {}

    def test_the_first_save_adds_the_photo(self, conn):
        a = tagged("a1", "Date/Year", desc="Immich title")
        im = VersionsImmich(assets={"a1": a})
        gr = FakeGramps(places=[place()])
        form = {"title": "Farm, 1923", "notes": "n", "place_gramps_id": "P0001",
                "date": {"value": "1923", "precision": "year"}, "links": ["https://example.org/x"]}
        events = save(gr, im, conn, "a1", form)
        [created] = gr.created
        gid = created["gramps_id"]
        created = gr.media[gid]
        assert conn.execute("SELECT gramps_id FROM minted_media WHERE source_id='a1'").fetchone()[0] == gid
        assert (created["desc"], created["date"]) == ("Farm, 1923", gdate(0, 0, 1923))
        assert sync_immich.media_links(created) == ["https://example.org/x"]
        assert gr.places[0]["media_list"][0]["ref"] == created["handle"]
        assert [n["text"]["string"] for n in gr.notes.values()] == ["n"]
        assert im.upserted == [f"ID/{gid}"]
        assert im.metadata["a1"]["bifrost"] == {"gramps_id": gid, "gramps_url": f"https://gramps.example/media/{gid}"}
        assert im.updated_assets == [("a1", {"description": "Farm, 1923"})]
        assert [e.action for e in events if e.entity == "media"][0] == "created"
        assert summary_of(events).data["created"] is True
        rec = load(gr, im, conn, "a1")
        assert rec["gramps"]["gramps_id"] == gid and rec["title"] == "Farm, 1923"

    def test_a_save_with_a_note_or_link_alone_adds_the_photo(self, conn):
        for form in ({"notes": "just a note"}, {"links": ["https://example.org/x"]}, {"place_gramps_id": "P0001"}):
            im = FakeImmich(assets={"a1": tagged("a1")})
            gr = FakeGramps(places=[place()])
            save(gr, im, conn, "a1", form)
            assert len(gr.created) == 1
            conn.execute("DELETE FROM minted_media")
            conn.commit()

    def test_a_save_with_nothing_filled_in_adds_nothing(self, conn):
        im = FakeImmich(assets={"a1": tagged("a1", desc="stale")})
        gr = FakeGramps()
        events = save(gr, im, conn, "a1", {"title": ""})
        assert gr.created == [] and conn.execute(
            "SELECT COUNT(*) FROM minted_media WHERE source_system IS NOT NULL").fetchone()[0] == 0
        assert im.updated_assets == [("a1", {"description": ""})]
        assert summary_of(events).data["gramps_id"] is None

    def test_a_chosen_code_is_taken_from_the_reserved_ones(self, conn):
        codes.claim(conn, "rsvd-22")
        im = FakeImmich(assets={"a1": tagged("a1")})
        gr = FakeGramps()
        assert codes.open_codes(conn, set())[0]["code"] == "RSVD22"
        save(gr, im, conn, "a1", {"title": "T", "notes": "Mine", "gramps_id": "RSVD22"})
        assert gr.created[0]["gramps_id"] == "RSVD22"
        assert [n["text"]["string"] for n in gr.notes.values()] == ["Mine"]
        assert codes.open_codes(conn, set()) == []
        row = conn.execute("SELECT source_system, source_id FROM minted_media WHERE gramps_id='RSVD22'").fetchone()
        assert tuple(row) == ("immich", "a1")

    def test_the_first_save_adopts_the_rows_bifrost_kept(self, conn):
        conn.execute("INSERT INTO photo_notes (asset_id, text, updated_at) VALUES ('a1', 'kept note', 't')")
        conn.execute("INSERT INTO photo_links (asset_id, url, added_at) VALUES ('a1', 'https://kept.example/x', 't')")
        conn.commit()
        im = FakeImmich(assets={"a1": tagged("a1", desc="T")})
        gr = FakeGramps()
        rec = load(gr, im, conn, "a1")
        assert (rec["notes"], [x["url"] for x in rec["links"]]) == ("kept note", ["https://kept.example/x"])
        save(gr, im, conn, "a1", {"title": "T", "notes": "kept note, edited", "links": ["https://kept.example/x"]})
        assert [n["text"]["string"] for n in gr.notes.values()] == ["kept note, edited"]
        assert sync_immich.media_links(gr.created[0]) == ["https://kept.example/x"]
        assert conn.execute("SELECT COUNT(*) FROM photo_notes").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM photo_links").fetchone()[0] == 0

    def test_the_immich_copy_failing_is_only_a_warning(self, conn):
        im, gr = self._registered(conn)

        async def boom(asset_id, **fields):
            raise ImmichError(500, "immich down")

        im.update_asset = boom
        events = save(gr, im, conn, "a1", {"title": "New", "change": 100})
        assert gr.media["ABC123"]["desc"] == "New"
        assert summary_of(events).data["warning"] == "Immich description not updated: immich down"
        assert [e.action for e in events if e.kind == "item" and e.entity == "media"] == ["updated", "skipped"]

    def test_a_stale_edit_is_refused(self, conn):
        im, gr = self._registered(conn)
        with pytest.raises(SyncError) as exc:
            save(gr, im, conn, "a1", {"title": "New", "change": 99})
        assert exc.value.status == 409 and "reload" in exc.value.detail
        assert gr.updated == [] and im.updated_assets == []
        save(gr, im, conn, "a1", {"title": "New", "change": 100})
        assert gr.media["ABC123"]["desc"] == "New"

    def test_an_unreachable_gramps_saves_nothing(self, conn):
        class DownGramps(FakeGramps):
            async def get_media_by_gramps_id(self, gid, backlinks=False):
                raise RuntimeError("connection refused")

        mint(conn, "ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", desc="Old")})
        with pytest.raises(SyncError) as exc:
            save(DownGramps(), im, conn, "a1", {"title": "New", "change": 100})
        assert exc.value.status == 502 and im.updated_assets == []
        rec = load(DownGramps(), im, conn, "a1")
        assert rec["gramps_error"].startswith("Gramps could not be read") and rec["title"] == "Old"

    def test_a_register_row_without_its_media_is_an_error(self, conn):
        mint(conn, "ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1")})
        with pytest.raises(SyncError) as exc:
            save(FakeGramps(), im, conn, "a1", {"title": "New"})
        assert exc.value.status == 404 and "not in Gramps" in exc.value.detail
        assert load(FakeGramps(), im, conn, "a1")["gramps_error"] == "the register points at ABC123, which is not in Gramps"

    def test_clearing_the_notes_removes_the_media_note(self, conn):
        im, gr = self._registered(conn)
        gr.notes["n-1"] = note("n-1", "old note")
        gr.notes["n-2"] = note("n-2", "second media note", gid="N0002")
        gr.media["ABC123"]["note_list"] = ["n-1", "n-2"]
        save(gr, im, conn, "a1", {"title": "Old title", "notes": "edited", "change": 100})
        assert gr.updated_notes[0]["handle"] == "n-1" and gr.updated_notes[0]["text"]["string"] == "edited"
        assert gr.notes["n-2"]["text"]["string"] == "second media note"
        save(gr, im, conn, "a1", {"title": "Old title", "notes": "", "change": 100})
        assert gr.media["ABC123"]["note_list"] == ["n-2"] and gr.deleted_notes == ["n-1"]

    def test_an_empty_title_falls_back_to_the_file_name(self, conn):
        im, gr = self._registered(conn)
        save(gr, im, conn, "a1", {"title": "", "notes": "n", "change": 100})
        assert gr.media["ABC123"]["desc"] == "img.jpg"

    def test_save_finishes_the_sync_work(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", desc="T")
        a["originalPath"] = "/up/moved.jpg"
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"ABC123": media()})
        events = save(gr, im, conn, "a1", {"title": "T", "change": 100})
        assert gr.media["ABC123"]["path"] == "immich/moved.jpg"
        assert im.upserted == ["ID/ABC123"]
        cols = [e.data["cols"] for e in events if e.entity == "media" and e.action == "updated"]
        assert set(cols[-1]) == {"file", "id tag"}

    def test_stack_variant_is_refused(self, conn):
        a = tagged("c1")
        a["stack"] = {"id": "s1", "primaryAssetId": "p1"}
        im = FakeImmich(assets={"c1": a})
        with pytest.raises(SyncError, match="stack variant"):
            save(FakeGramps(), im, conn, "c1", {"title": "x"})


class TestPlaces:
    def _registered(self, conn, holding=("h1",), second=()):
        mint(conn, "ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "ID/ABC123", desc="T")})
        gr = FakeGramps({"ABC123": media()},
                        places=[place(holding=holding), place("P0002", "Taylors Falls", holding=second)])
        return im, gr

    def test_the_place_is_the_gallery_holding_the_photo(self, conn):
        im, gr = self._registered(conn)
        rec = load(gr, im, conn, "a1")
        assert rec["place"]["gramps_id"] == "P0001" and rec["place"]["name"] == "Chisago Lake"

    def test_changing_the_place_moves_the_photo(self, conn):
        im, gr = self._registered(conn)
        events = save(gr, im, conn, "a1", {"title": "T", "place_gramps_id": "P0002", "change": 100})
        assert gr.places[0]["media_list"] == [] and gr.places[1]["media_list"][0]["ref"] == "h1"
        assert [p["gramps_id"] for p in gr.updated_places] == ["P0001", "P0002"]
        assert events_of(events, "place") == [("updated", {}, "added to the gallery")]
        assert load(gr, im, conn, "a1")["place"]["gramps_id"] == "P0002"
        save(gr, im, conn, "a1", {"title": "T", "place_gramps_id": "P0002", "change": 100})
        assert len(gr.updated_places) == 2

    def test_clearing_the_place_takes_the_photo_out(self, conn):
        im, gr = self._registered(conn)
        save(gr, im, conn, "a1", {"title": "T", "change": 100})
        assert gr.places[0]["media_list"] == []
        assert load(gr, im, conn, "a1")["place"] is None

    def test_an_unknown_place_is_refused_before_anything_is_written(self, conn):
        im, gr = self._registered(conn)
        with pytest.raises(SyncError, match="names no Gramps place"):
            save(gr, im, conn, "a1", {"title": "New", "place_gramps_id": "P0404", "change": 100})
        assert gr.updated == []

    def test_a_photo_in_several_galleries_is_left_alone(self, conn):
        im, gr = self._registered(conn, holding=("h1",), second=("h1",))
        rec = load(gr, im, conn, "a1")
        assert rec["place"] is None and [p["gramps_id"] for p in rec["places"]] == ["P0001", "P0002"]
        save(gr, im, conn, "a1", {"title": "T", "change": 100})
        assert gr.updated_places == []
        assert [len(p["media_list"]) for p in gr.places] == [1, 1]


class TestLoad:
    def test_an_unregistered_photo_opens_with_its_immich_title_and_nothing_else(self, conn):
        a = tagged("a1", "Sync/Gramps", desc="Immich title")
        a["exifInfo"].update({"latitude": 45.5, "longitude": -92.9})
        rec = load(FakeGramps(places=[place()]), FakeImmich(assets={"a1": a}), conn, "a1")
        assert (rec["title"], rec["date"], rec["gramps"], rec["change"]) == ("Immich title", None, None, None)
        assert (rec["place"], rec["places"]) == (None, [])
        assert (rec["notes"], rec["links"], rec["date_readonly"]) == ("", [], None)
        assert rec["immich_date"] == "1923-06-15"

    def test_a_registered_photo_opens_with_what_gramps_has(self, conn):
        mint(conn, "ABC123", "a1")
        gr = FakeGramps({"ABC123": media(desc="Gramps title", date=gdate(0, 0, 1923, modifier=1), change=7,
                                         note_list=["n-r", "n-1"],
                                         attribute_list=[sync_immich._attr("Source URL", "https://example.org/x")])})
        gr.notes["n-r"] = note("n-r", "research", kind="Research")
        gr.notes["n-1"] = note("n-1", "the media note")
        rec = load(gr, FakeImmich(assets={"a1": tagged("a1", desc="Immich title")}), conn, "a1")
        assert (rec["title"], rec["date"]["display"], rec["notes"], rec["change"]) == (
            "Gramps title", "Before 1923", "the media note", 7)
        assert [x["url"] for x in rec["links"]] == ["https://example.org/x"]
        assert rec["gramps"] == {"gramps_id": "ABC123", "url": "https://gramps.example/media/ABC123"}

    def test_a_date_the_form_cannot_hold_is_read_only_until_a_new_one_is_entered(self, conn):
        mint(conn, "ABC123", "a1")
        textonly = {"_class": "Date", "dateval": [0, 0, 0, False], "modifier": 6, "quality": 0,
                    "text": "the summer Ed left"}
        im = FakeImmich(assets={"a1": tagged("a1", desc="T")})
        gr = FakeGramps({"ABC123": media(date=textonly)})
        rec = load(gr, im, conn, "a1")
        assert (rec["date"], rec["date_readonly"]) == (None, "the summer Ed left")
        save(gr, im, conn, "a1", {"title": "New", "change": 100})
        assert gr.media["ABC123"]["date"] == textonly
        save(gr, im, conn, "a1", {"title": "New", "date": {"value": "1923"}, "change": 101})
        assert gr.media["ABC123"]["date"] == gdate(0, 0, 1923)

    def test_clearing_a_held_date_empties_it(self, conn):
        mint(conn, "ABC123", "a1")
        im = VersionsImmich(assets={"a1": tagged("a1", desc="T")})
        gr = FakeGramps({"ABC123": media(date=gdate(0, 0, 1923))})
        save(gr, im, conn, "a1", {"title": "T", "change": 100})
        assert gr.media["ABC123"]["date"] == dates.EMPTY_DATE
        rec = load(gr, im, conn, "a1")
        assert rec["date"] is None and rec["date_readonly"] is None and rec["immich_date"] == "1923-06-15"
        assert im.untagged_assets == []


class TestMergedSpelling:
    def test_merged_copies_keep_tag_spelling(self):
        owner = {"id": "a1", "ownerId": "u1", "tags": [{"value": "ID/ABC123"}, {"value": "Sync/Gramps"}]}
        partner = {"id": "a1", "ownerId": "u1", "tags": [{"value": "Holiday"}]}
        merged = sync_immich._merge_copies([("u1", owner), ("u2", partner)])
        assert [t["value"] for t in merged["tags"]] == ["Holiday", "ID/ABC123", "Sync/Gramps"]


class TestLeftoverRows:
    def test_a_created_media_takes_the_note_and_links_bifrost_kept(self, conn):
        conn.execute("INSERT INTO photo_notes (asset_id, text, updated_at) VALUES ('a1', 'Written before', 't')")
        conn.execute("INSERT INTO photo_links (asset_id, url, added_at) VALUES ('a1', 'https://kept.example/x', 't')")
        conn.commit()
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps", desc="img.jpg")}, tagged={"a1"})
        gr = FakeGramps()
        events = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert [(e.entity, e.action) for e in events if e.kind == "item" and e.entity != "tag"] == [
            ("media", "created"), ("note", "created"), ("media", "updated")]
        [note_obj] = gr.notes.values()
        assert note_obj["type"] == "Media Note" and note_obj["text"]["string"] == "Written before"
        assert gr.media[gr.created[0]["gramps_id"]]["note_list"] == [note_obj["handle"]]
        assert sync_immich.media_links(gr.media[gr.created[0]["gramps_id"]]) == ["https://kept.example/x"]
        assert conn.execute("SELECT COUNT(*) FROM photo_notes").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM photo_links").fetchone()[0] == 0
        assert "notes" not in im.metadata["a1"]["bifrost"]
        assert summary_of(events).data["notes_synced"] == 1
        again = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert [e for e in again if e.kind == "item"] == []

    def test_a_url_only_note_becomes_a_link(self, conn):
        conn.execute("INSERT INTO photo_notes (asset_id, text, updated_at) VALUES ('a1', ' https://only.example/y ', 't')")
        conn.commit()
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps")}, tagged={"a1"})
        gr = FakeGramps()
        run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert gr.notes == {}
        assert sync_immich.media_links(gr.created[0]) == ["https://only.example/y"]

    def test_the_sync_no_longer_pushes_rows_for_registered_media(self, conn):
        mint(conn, "ABC123", "a1")
        conn.execute("INSERT INTO photo_notes (asset_id, gramps_id, text, updated_at) VALUES ('a1', 'ABC123', 'kept', 't')")
        conn.commit()
        im = FakeImmich(assets={"a1": tagged("a1", "ID/ABC123", desc="T")})
        gr = FakeGramps({"ABC123": media()})
        events = run_scan(im, gr, conn, apply=True, cfg=CFG)
        assert gr.notes == {} and gr.updated == []
        assert summary_of(events).data["skipped"] == 1
        assert conn.execute("SELECT COUNT(*) FROM photo_notes").fetchone()[0] == 1


class TestPendingSync:
    def pending(self, im, gr, conn):
        return run(photos.pending_changes(gr, [im], conn, CFG, "a1"))

    def test_in_step_with_gramps(self, conn):
        mint(conn, "ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "ID/ABC123", desc="T")})
        assert self.pending(im, FakeGramps({"ABC123": media()}), conn) == []

    def test_title_date_place_and_notes_are_never_pending(self, conn):
        mint(conn, "ABC123", "a1")
        conn.execute("INSERT INTO photo_notes (asset_id, gramps_id, text, updated_at) VALUES ('a1', 'ABC123', 'n', 't')")
        conn.commit()
        a = tagged("a1", "ID/ABC123", desc="Easter 1966")
        a["exifInfo"].update({"latitude": 45.5, "longitude": -92.9})
        im = FakeImmich(assets={"a1": a})
        gr = FakeGramps({"ABC123": media()}, places=[place()])
        assert self.pending(im, gr, conn) == []

    def test_file_and_face_changes_are_pending(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "ID/ABC123", desc="T")
        a["originalPath"] = "/up/moved.jpg"
        im = FakeImmich(assets={"a1": a}, faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"},
                                                        "boundingBoxX1": 10, "boundingBoxY1": 10,
                                                        "boundingBoxX2": 50, "boundingBoxY2": 50,
                                                        "imageWidth": 100, "imageHeight": 100}]})
        gr = FakeGramps({"ABC123": media()}, people={"h-ed": linked("h-ed", "uuid-ed")})
        assert self.pending(im, gr, conn) == ["faces", "file"]

    def test_a_photo_outside_gramps_has_nothing_pending(self, conn):
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps")})
        assert self.pending(im, FakeGramps(), conn) == []


class TestLinkRecord:
    def test_create_writes_the_record(self, conn):
        im = FakeImmich(assets={"a1": tagged("a1", "Sync/Gramps")}, tagged={"a1"})
        gr = FakeGramps()
        run_scan(im, gr, conn, apply=True, cfg=CFG)
        gid = gr.created[0]["gramps_id"]
        assert im.metadata["a1"]["bifrost"] == {"gramps_id": gid,
                                                "gramps_url": f"https://gramps.example/media/{gid}"}

    def test_single_asset_update_copies_the_gramps_title_to_immich(self, conn):
        mint(conn, "ABC123", "a1")
        im = FakeImmich(assets={"a1": tagged("a1", "ID/ABC123", desc="Immich title")})
        gr = FakeGramps({"ABC123": media(desc="Gramps title")})

        async def collect(update):
            return [e async for e in sync_immich.sync_one_asset(
                gr, [im], conn, CFG, "a1", update=update)]

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

    def test_add_version_stacks_and_matches(self, conn):
        a = self._primary()
        n = tagged("n1", "Date/Month", desc="raw scan", when="2020-01-01T12:00:00Z")
        n.update({"width": 1000, "height": 800, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "n1": n}, faces={"a1": [face("p-ed", 100, 100, 300, 300)]})
        im.metadata["a1"] = {"bifrost": {"gramps_id": "ABC123"}}
        rec = run(photos.add_version(FakeGramps(), [im], conn, CFG, "a1", "n1"))
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

    def test_an_upload_joins_as_a_version_with_the_main_tags(self, conn):
        im = VersionsImmich(assets={"a1": self._primary()})
        new_id, rec = run(photos.upload_version(FakeGramps(), [im], conn, CFG, "a1", "rescan.tif",
                                                io.BytesIO(b"tif"), "2026-09-22T10:00:00Z"))
        assert new_id == "u1" and im.uploads == [("rescan.tif", b"tif", "2026-09-22T10:00:00Z")]
        assert im.created_stacks == [["a1", "u1"]]
        assert [(m["asset_id"], m["drift"]) for m in rec["versions"]["members"]] == [("a1", []), ("u1", [])]
        assert "description" not in im.assets["u1"]["exifInfo"]
        assert sorted(t["value"] for t in im.assets["u1"]["tags"]) == ["ID/ABC123", "Sync/Date", "Sync/Gramps"]

    def test_add_version_refuses_stacked_foreign_or_self(self, conn):
        a = self._primary()
        other = tagged("o1")
        other.update({"ownerId": "someone-else"})
        busy = tagged("b1")
        busy.update({"ownerId": "me-1", "stack": {"id": "s9", "primaryAssetId": "b1"}})
        im = VersionsImmich(assets={"a1": a, "o1": other, "b1": busy})
        for target, msg in (("o1", "same Immich account"), ("b1", "already in a stack"), ("a1", "main image")):
            with pytest.raises(SyncError, match=msg):
                run(photos.add_version(FakeGramps(), [im], conn, CFG, "a1", target))
        assert im.created_stacks == []

    def test_drift_is_reported_and_match_fixes_it(self, conn):
        a = self._primary()
        v = tagged("v1", "Sync/Gramps", "Date/Month", desc="old title")
        v.update({"width": 1000, "height": 800, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        rec = load(FakeGramps(), im, conn, "a1")
        assert rec["versions"]["members"][1]["drift"] == ["location", "tags (missing ID/ABC123, Sync/Date)"]
        rec = run(photos.match_member(FakeGramps(), [im], conn, CFG, "a1", "v1"))
        assert rec["versions"]["members"][1]["drift"] == []
        assert im.untagged_assets == [] and v["exifInfo"]["description"] == "old title"

    def test_remove_unstacks_and_strips_identity_tags(self, conn):
        a = self._primary()
        v = tagged("v1", "Sync/Gramps", "ID/ABC123", "Date/Year", "Holiday")
        v.update({"ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        with pytest.raises(SyncError, match="make another version the main image"):
            run(photos.remove_version(FakeGramps(), [im], conn, CFG, "a1", "a1"))
        rec = run(photos.remove_version(FakeGramps(), [im], conn, CFG, "a1", "v1"))
        assert im.removed == [("s1", "v1")]
        assert sorted(t["value"] for t in v["tags"]) == ["Date/Year", "Holiday"]
        assert [m["asset_id"] for m in rec["versions"]["members"]] == ["a1"]

    def test_promote_switches_main_and_the_sync_repoints(self, conn):
        mint(conn, "ABC123", "a1")
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
        new_main = run(photos.promote([im], conn, CFG, gr, "a1", "v1", redraw_faces=True))
        assert new_main == "v1"
        assert im.primary_changes == [("s1", "v1")]
        assert im.reassigned == [("uuid-ed", "d1")]
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
        rec = load(FakeGramps({"ABC123": media()}), im, conn, "a1")
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

    def test_slots_stay_put(self, conn):
        c = pc.create(conn, "Farm")
        pc.add_items(conn, c["id"], ["a1", "b1"])
        assert pc.slots(conn, c["id"]) == {"a1": 1, "b1": 2}
        assert pc.move_item(conn, c["id"], "b1", 5) == {"a1": 1, "b1": 5}
        pc.add_items(conn, c["id"], ["c1"])
        pc.remove_item(conn, c["id"], "a1")
        assert pc.slots(conn, c["id"]) == {"b1": 5, "c1": 6}
        assert pc.item_ids(conn, c["id"]) == ["b1", "c1"]

    def test_moving_onto_a_photo_swaps_the_two(self, conn):
        c = pc.create(conn, "Farm")
        pc.add_items(conn, c["id"], ["a1", "b1", "c1"])
        assert pc.move_item(conn, c["id"], "c1", 1) == {"c1": 1, "b1": 2, "a1": 3}

    def test_move_item_clamps_and_ignores_strangers(self, conn):
        c = pc.create(conn, "Farm")
        pc.add_items(conn, c["id"], ["a1", "b1"])
        assert pc.move_item(conn, c["id"], "a1", 0) == {"a1": 1, "b1": 2}
        assert pc.move_item(conn, c["id"], "a1", 10_000) == {"b1": 2, "a1": pc.MAX_ITEMS}
        assert pc.move_item(conn, c["id"], "zz", 1) is None

    def test_new_photos_go_after_the_last_slot_then_into_gaps(self, conn):
        c = pc.create(conn, "Farm")
        pc.add_items(conn, c["id"], ["a1"])
        pc.move_item(conn, c["id"], "a1", pc.MAX_ITEMS)
        pc.add_items(conn, c["id"], ["b1", "c1"])
        assert pc.slots(conn, c["id"]) == {"b1": 1, "c1": 2, "a1": pc.MAX_ITEMS}

    def test_migration_turns_the_old_order_into_slots(self, conn):
        c = pc.create(conn, "Old")
        conn.executemany("INSERT INTO collection_items (collection_id, asset_id, seq, added_at) VALUES (?, ?, ?, ?)",
                         [(c["id"], "b1", 2, "t"), (c["id"], "a1", 0, "t"), (c["id"], "c1", 7, "t")])
        conn.executescript(db.MIGRATIONS[13])
        assert pc.slots(conn, c["id"]) == {"a1": 1, "b1": 2, "c1": 3}

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

    def test_a_collection_gives_a_variants_place_to_its_main_image(self, conn):
        im = VersionsImmich(assets={a: tagged(a) for a in ("a1", "v1", "b1", "w1", "x1")})
        stacked(im, "a1", "v1")
        stacked(im, "b1", "w1")
        one = pc.create(conn, "One")
        pc.add_items(conn, one["id"], ["x1", "v1", "b1", "w1"])
        assert run(photos.fold_stacked_items([im], conn, one["id"])) == ["x1", "a1", "b1"]

    def test_a_variant_opens_as_its_main_image_and_brings_its_collections(self, conn):
        im = VersionsImmich(assets={"a1": tagged("a1", desc="Main"), "v1": tagged("v1", desc="Variant")})
        stacked(im, "a1", "v1")
        c = pc.create(conn, "Grund History")
        pc.add_items(conn, c["id"], ["v1"])
        rec = load(FakeGramps(), im, conn, "v1")
        assert (rec["asset_id"], rec["title"]) == ("a1", "Main")
        assert rec["collections"] == [{"id": c["id"], "name": "Grund History"}]
        assert pc.item_ids(conn, c["id"]) == ["a1"]

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
        rec = load(FakeGramps(), im, conn, "v1")
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
        rows = run(photos.search([fh], conn, mode="synced", browse=[fh]))["items"]
        assert [i["asset_id"] for i in rows] == ["a1", "b1"]
        me = VersionsImmich(assets={"a1": a, "b1": b}, me_id="u-me")
        me.label = "me"
        rows = run(photos.search([fh, me], conn, mode="synced", browse=[fh]))["items"]
        assert [i["asset_id"] for i in rows] == ["a1"]


class TestVersionLabels:
    def test_the_label_lives_in_the_immich_record_alone(self, conn):
        a = tagged("a1")
        a.update({"ownerId": "me-1"})
        v = tagged("v1")
        v.update({"ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        im.metadata["v1"] = {"bifrost": {"gramps_id": "ABC123"}}
        run(photos.set_version_label([im], "v1", "  screenshot version "))
        assert im.metadata["v1"]["bifrost"] == {"gramps_id": "ABC123", "version_label": "screenshot version"}
        rec = load(FakeGramps(), im, conn, "a1")
        assert [(m["asset_id"], m["label"]) for m in rec["versions"]["members"]] == [("a1", ""), ("v1", "screenshot version")]
        run(photos.set_version_label([im], "a1", "the edited original"))
        assert im.metadata["a1"]["bifrost"] == {"version_label": "the edited original"}
        assert load(FakeGramps(), im, conn, "a1")["label"] == "the edited original"
        run(photos.set_version_label([im], "a1", ""))
        assert im.metadata["a1"] == {}
        assert load(FakeGramps(), im, conn, "a1")["label"] == ""
        assert "version_labels" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}

    def test_match_keeps_the_target_label_and_drops_the_sources(self, conn):
        a = tagged("a1", "Sync/Gramps", desc="T")
        a.update({"width": 100, "height": 80, "ownerId": "me-1"})
        v = tagged("v1", desc="old")
        v.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        im.metadata["a1"] = {"bifrost": {"gramps_id": "ABC123", "version_label": "main scan"}}
        run(photos.set_version_label([im], "v1", "raw"))
        run(photos.match_member(FakeGramps(), [im], conn, CFG, "a1", "v1"))
        assert im.metadata["v1"]["bifrost"] == {"gramps_id": "ABC123", "version_label": "raw"}

    def test_the_sync_record_carries_the_label_and_no_notes(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", desc="T")
        im = VersionsImmich(assets={"a1": a})
        run(photos.set_version_label([im], "a1", "edited"))
        save(FakeGramps({"ABC123": media()}), im, conn, "a1", {"title": "T", "notes": "n", "change": 100})
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

    def test_links_are_source_url_attributes_on_the_media(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", "ID/ABC123", desc="T")
        a.update({"width": 100, "height": 80, "ownerId": "me-1"})
        v = tagged("v1")
        v.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        gr = FakeGramps({"ABC123": media()})
        save(gr, im, conn, "a1", {"title": "T", "change": 100,
                                 "links": [" https://example.org/box-3 ", "http://example.org/other"]})
        assert [(x["type"], x["value"]) for x in gr.media["ABC123"]["attribute_list"]] == [
            ("Immich ID", "a1"), ("Source URL", "https://example.org/box-3"), ("Source URL", "http://example.org/other")]
        rec = load(gr, im, conn, "a1")
        assert [x["url"] for x in rec["links"]] == ["https://example.org/box-3", "http://example.org/other"]
        run(photos.promote([im], conn, CFG, gr, "a1", "v1", redraw_faces=False))
        assert [x["url"] for x in load(gr, im, conn, "v1")["links"]] == ["https://example.org/box-3", "http://example.org/other"]
        save(gr, im, conn, "v1", {"title": "T", "change": 101, "links": ["http://example.org/other"]})
        assert sync_immich.media_links(gr.media["ABC123"]) == ["http://example.org/other"]

    def test_api(self, conn):
        from types import SimpleNamespace
        import httpx
        from fastapi import FastAPI
        from bifrost.web.routes import photos as photos_routes
        mint(conn, "ABC123", "a1")
        app = FastAPI()
        app.include_router(photos_routes.router)
        app.state.conn = conn
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
        assert conn.execute("SELECT job, status FROM runs").fetchall()[0][:] == ("photos.save", "ok")
        r = call("PUT", "/photos/api/photo/a1", json={"title": "T", "links": ["x"], "change": 101})
        assert r.status_code == 400 and "http" in r.json()["detail"]
        r = call("PUT", "/photos/api/photo/a1", json={"title": "T", "change": 100})
        assert r.status_code == 409 and "reload" in r.json()["detail"]
        assert call("GET", "/photos/api/photo/a1/pending").json() == {"changes": []}


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


class TestVersionsStayTheirOwn:
    def test_save_leaves_the_versions_title_and_date_alone(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "Sync/Gramps", "ID/ABC123", desc="old")
        a.update({"width": 100, "height": 80, "ownerId": "me-1"})
        v = tagged("v1", "Sync/Gramps", desc="raw scan", when="2020-01-01T12:00:00Z")
        v.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        gr = FakeGramps({"ABC123": media(desc="old")})
        save(gr, im, conn, "a1", {"title": "new title", "date": {"value": "1923"}, "change": 100})
        assert gr.media["ABC123"]["desc"] == "new title"
        assert a["exifInfo"]["description"] == "new title"
        assert v["exifInfo"]["description"] == "raw scan" and v["localDateTime"] == "2020-01-01T12:00:00Z"
        assert sorted(t["value"] for t in v["tags"]) == ["ID/ABC123", "Sync/Gramps"]
        rec = load(gr, im, conn, "a1")
        assert rec["versions"]["members"][1]["drift"] == []


class TestSyncedVersionLeads:
    def _pair(self, conn):
        mint(conn, "ABC123", "s1")
        unsynced = tagged("u1", "Sync/Gramps", desc="unsynced title")
        unsynced.update({"width": 100, "height": 80, "ownerId": "me-1"})
        synced = tagged("s1", "Sync/Gramps", "Sync/Date", "Date/Year", "ID/ABC123", desc="synced title")
        synced.update({"width": 100, "height": 80, "ownerId": "me-1"})
        return unsynced, synced

    def test_the_gramps_photo_becomes_the_main(self, conn):
        unsynced, synced = self._pair(conn)
        c = pc.create(conn, "Album")
        pc.add_items(conn, c["id"], ["u1"])
        im = VersionsImmich(assets={"u1": unsynced, "s1": synced})
        gr = FakeGramps({"ABC123": media(desc="synced title")})
        rec = run(photos.add_version(gr, [im], conn, CFG, "u1", "s1"))
        assert im.created_stacks == [["s1", "u1"]]
        assert rec["asset_id"] == "s1" and rec["gramps"]["gramps_id"] == "ABC123"
        assert [(m["asset_id"], m["is_primary"], m["drift"]) for m in rec["versions"]["members"]] == [
            ("s1", True, []), ("u1", False, [])]
        assert unsynced["exifInfo"]["description"] == "unsynced title"
        assert sorted(t["value"] for t in unsynced["tags"]) == ["ID/ABC123", "Sync/Date", "Sync/Gramps"]
        assert rec["title"] == "synced title"
        assert pc.item_ids(conn, c["id"]) == ["s1"]

    def test_two_gramps_photos_cannot_share_a_stack(self, conn):
        unsynced, synced = self._pair(conn)
        mint(conn, "XYZ789", "u1")
        im = VersionsImmich(assets={"u1": unsynced, "s1": synced})
        with pytest.raises(SyncError, match="both photos are already in Gramps"):
            run(photos.add_version(FakeGramps(), [im], conn, CFG, "u1", "s1"))
        assert im.created_stacks == []
