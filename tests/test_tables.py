"""Table grids: validation, storage, geometry, page images, transcription"""

import asyncio
import io

import pytest
from PIL import Image

from bifrost.core import db
from bifrost.core.clients import GeminiError
from bifrost.modules import tables


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


@pytest.fixture(autouse=True)
def fresh_caches(monkeypatch):
    monkeypatch.setattr(tables, "SOURCES", tables._Lru(3))
    monkeypatch.setattr(tables, "IMAGES", tables._Lru(16))


def grid(ncols=3, nrows=4, **kw):
    g = {
        "frame": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]],
        "cols": [{"id": f"c{i}", "name": f"Col {i}", "u": [i / ncols, i / ncols]} for i in range(ncols)],
        "rows": [{"id": f"r{j}", "v": [j / nrows, j / nrows]} for j in range(nrows)],
        "first_line": 1,
        "group_col": None,
        "cells": {},
    }
    g.update(kw)
    return g


def jpeg(w=400, h=300, color=(200, 190, 170), **kw) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG", **kw)
    return buf.getvalue()


def pdf(*sizes, dpi=150) -> bytes:
    pages = [Image.new("RGB", s, (230, 220, 190)) for s in sizes]
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:], resolution=dpi)
    return buf.getvalue()


class TestNormalize:
    def test_round_trip_tidies_names_values_and_ids(self):
        raw = grid(cells={"r0": {"c0": "  71 ", "c1": "", "zz": "x"}, "gone": {"c0": "y"},
                          "r1": {"c2": 42}})
        raw["cols"][1]["name"] = "  Name of  each\nperson "
        raw["group_col"] = "c0"
        out = tables.normalize_grid(raw)
        assert out["cols"][1]["name"] == "Name of each person"
        assert out["cells"] == {"r0": {"c0": "71"}, "r1": {"c2": "42"}}
        assert out["group_col"] == "c0"

    def test_first_lines_sit_on_the_frame_and_corners_are_clamped(self):
        raw = grid()
        raw["cols"][0]["u"] = [0.3, 0.4]
        raw["rows"][0]["v"] = [0.1, 0.1]
        raw["frame"][2] = [1.4, -0.2]
        out = tables.normalize_grid(raw)
        assert out["cols"][0]["u"] == [0.0, 0.0] and out["rows"][0]["v"] == [0.0, 0.0]
        assert out["frame"][2] == [1.0, 0.0]

    def test_translations_ride_along_with_names_and_values(self):
        raw = grid(cells={"r0": {"c0": "Hustru"}}, trans={"r0": {"c0": " Wife ", "c1": ""}, "gone": {"c0": "x"}})
        raw["cols"][0]["trans"] = "  Relation\nto head "
        out = tables.normalize_grid(raw)
        assert out["cols"][0]["trans"] == "Relation to head" and out["cols"][1]["trans"] == ""
        assert out["trans"] == {"r0": {"c0": "Wife"}}
        with pytest.raises(tables.GridError, match="translations are not an object"):
            tables.normalize_grid(grid(trans=["x"]))

    def test_person_links_keep_only_known_cells_and_handles(self):
        raw = grid(people={"r0": {"c0": "2b95ac4660404d47", "c1": "bad handle!", "zz": "abc"},
                           "gone": {"c0": "abc"}, "r1": {"c2": 7}})
        assert tables.normalize_grid(raw)["people"] == {"r0": {"c0": "2b95ac4660404d47"}}
        with pytest.raises(tables.GridError, match="person links"):
            tables.normalize_grid(grid(people=["x"]))

    def test_unknown_group_column_is_dropped(self):
        assert tables.normalize_grid(grid(group_col="nope"))["group_col"] is None

    @pytest.mark.parametrize("patch,message", [
        ({"frame": [[0, 0], [1, 0], [1, 1]]}, "four corners"),
        ({"cols": []}, "at least one column"),
        ({"first_line": "x"}, "whole number"),
        ({"cells": []}, "not an object"),
    ])
    def test_refusals(self, patch, message):
        with pytest.raises(tables.GridError, match=message):
            tables.normalize_grid(grid(**patch))

    def test_lines_out_of_order_are_refused(self):
        raw = grid()
        raw["cols"][2]["u"] = [0.2, 0.9]
        with pytest.raises(tables.GridError, match="out of order"):
            tables.normalize_grid(raw)

    def test_repeated_ids_are_refused(self):
        raw = grid()
        raw["rows"][2]["id"] = "r1"
        with pytest.raises(tables.GridError, match="repeated id"):
            tables.normalize_grid(raw)

    def test_long_values_are_refused(self):
        with pytest.raises(tables.GridError, match="longer than"):
            tables.normalize_grid(grid(cells={"r0": {"c0": "x" * (tables.VALUE_MAX + 1)}}))


class TestStorage:
    def test_save_needs_the_current_rev(self, conn):
        first = tables.save_table(conn, 8, 1, grid(), 0, "1910 census")
        assert first["rev"] == 1
        with pytest.raises(tables.Conflict):
            tables.save_table(conn, 8, 1, grid(), 0)
        second = tables.save_table(conn, 8, 1, grid(ncols=2), 1)
        assert second["rev"] == 2
        saved = tables.get_table(conn, 8, 1)
        assert saved["rev"] == 2 and len(saved["grid"]["cols"]) == 2

    def test_title_survives_saves_without_one_and_follows_paperless(self, conn):
        tables.save_table(conn, 8, 1, grid(), 0, "Old")
        tables.save_table(conn, 8, 1, grid(), 1)
        assert tables.list_tables(conn)[0]["title"] == "Old"
        tables.set_title(conn, 8, "New")
        assert tables.list_tables(conn)[0]["title"] == "New"

    def test_delete_checks_the_rev(self, conn):
        tables.save_table(conn, 8, 2, grid(), 0)
        with pytest.raises(tables.Conflict):
            tables.delete_table(conn, 8, 2, 5)
        tables.delete_table(conn, 8, 2, 1)
        assert tables.get_table(conn, 8, 2) is None
        tables.save_table(conn, 8, 2, grid(), 0)

    def test_list_counts_lines_columns_and_values(self, conn):
        tables.save_table(conn, 8, 1, grid(cells={"r0": {"c0": "a", "c1": "b"}, "r1": {"c0": "c"}}), 0, "T")
        tables.save_table(conn, 8, 3, grid(), 0, "T")
        assert tables.table_pages(conn, 8) == [1, 3]
        item = next(i for i in tables.list_tables(conn) if i["page"] == 1)
        assert (item["lines"], item["columns"], item["filled"]) == (4, 3, 3)

    def test_translations_option_follows_the_data_until_set(self, conn):
        assert tables.doc_options(conn, 8) == {"translations": False}
        tables.save_table(conn, 8, 2, grid(trans={"r0": {"c0": "Wife"}}), 0)
        assert tables.doc_options(conn, 8) == {"translations": True}
        assert tables.set_doc_options(conn, 8, False) == {"translations": False}
        assert tables.doc_options(conn, 8) == {"translations": False}
        assert tables.doc_options(conn, 9) == {"translations": False}

    def test_csv_has_line_numbers_and_column_names(self):
        g = grid(ncols=2, nrows=2, first_line=51, cells={"r1": {"c1": "Farmer"}})
        g["cols"][0]["name"] = ""
        assert tables.to_csv(g).splitlines() == ["Line,Column 1,Col 1", "51,,", "52,,Farmer"]

    def test_csv_pairs_each_column_with_its_translation(self):
        g = grid(ncols=2, nrows=1, cells={"r0": {"c0": "Hustru", "c1": "37"}}, trans={"r0": {"c0": "Wife"}})
        g["cols"][0]["trans"] = "Relation"
        assert tables.to_csv(g).splitlines() == [
            "Line,Col 0,Relation,Col 1,Col 1 (translation)", "1,Hustru,Wife,37,"]

    def test_notes_are_kept_per_page(self, conn):
        first = tables.add_note(conn, 10, 1, 0.25, 0.5, "  Medium height\nslender  ", "Draft card")
        tables.add_note(conn, 10, 2, 0.1, 0.1, "back side")
        assert first["text"] == "Medium height\nslender" and (first["x"], first["y"]) == (0.25, 0.5)
        assert [n["text"] for n in tables.list_notes(conn, 10, 1)] == ["Medium height\nslender"]
        with pytest.raises(ValueError, match="needs text"):
            tables.add_note(conn, 10, 1, 0.2, 0.2, "   ")
        with pytest.raises(ValueError, match="not a number"):
            tables.add_note(conn, 10, 1, None, 0.2, "x")

    def test_moving_a_note_keeps_its_date_and_editing_changes_it(self, conn, monkeypatch):
        monkeypatch.setattr(tables, "_now", lambda: "2026-10-06T10:00:00")
        note = tables.add_note(conn, 10, 1, 0.2, 0.2, "first")
        monkeypatch.setattr(tables, "_now", lambda: "2026-10-07T10:00:00")
        moved = tables.update_note(conn, note["id"], x=1.7)
        assert (moved["x"], moved["y"], moved["updated_at"]) == (1.0, 0.2, "2026-10-06T10:00:00")
        edited = tables.update_note(conn, note["id"], text="second")
        assert (edited["text"], edited["updated_at"]) == ("second", "2026-10-07T10:00:00")
        with pytest.raises(ValueError):
            tables.update_note(conn, note["id"], text=" ", x=0.5)
        assert tables.get_note(conn, note["id"])["x"] == 1.0
        assert tables.update_note(conn, 999, text="x") is None
        assert tables.delete_note(conn, note["id"]) and not tables.delete_note(conn, note["id"])

    def test_list_includes_pages_that_only_have_notes(self, conn):
        tables.save_table(conn, 8, 1, grid(), 0, "Census")
        tables.add_note(conn, 8, 1, 0.5, 0.5, "on the table page")
        tables.add_note(conn, 10, 1, 0.5, 0.5, "a", "Old title")
        tables.add_note(conn, 10, 1, 0.6, 0.5, "b", "Old title")
        tables.set_title(conn, 10, "Draft card")
        items = {(t["doc_id"], t["page"]): t for t in tables.list_tables(conn)}
        assert items[(8, 1)]["table"] and items[(8, 1)]["notes"] == 1
        card = items[(10, 1)]
        assert (card["table"], card["notes"], card["title"], card["lines"]) == (False, 2, "Draft card", 0)


class TestGeometry:
    def test_rectangle_points(self):
        pts = tables.grid_points(grid(ncols=2, nrows=2))
        assert len(pts) == 3 and len(pts[0]) == 3
        assert pts[0][0] == pytest.approx((0.1, 0.2))
        assert pts[1][1] == pytest.approx((0.5, 0.5))
        assert pts[2][2] == pytest.approx((0.9, 0.8))

    def test_slanted_lines_meet_where_they_cross(self):
        g = grid(ncols=2, nrows=2)
        g["frame"] = [[0.1, 0.1], [0.9, 0.2], [0.8, 0.9], [0.0, 0.8]]
        g["cols"][1]["u"] = [0.25, 0.75]
        pts = tables.grid_points(g)
        top = tables.col_segment(g["frame"], [0.25, 0.75])
        mid = tables.row_segment(g["frame"], [0.5, 0.5])
        x, y = pts[1][1]
        for (ax, ay), (bx, by) in (top, mid):
            assert (bx - ax) * (y - ay) - (by - ay) * (x - ax) == pytest.approx(0, abs=1e-12)


class TestPages:
    def test_browser_images_pass_through(self):
        data = jpeg()
        assert tables.page_bytes(data, "image/jpeg", 1) == (data, "image/jpeg")

    def test_pdf_pages_render_at_the_scan_resolution(self):
        data = pdf((2200, 1500), (1100, 800))
        assert tables.page_count(data, "application/pdf") == 2
        assert tables.page_image(data, "application/pdf", 1).size == (2200, 1500)
        out, mime = tables.page_bytes(data, "application/pdf", 2)
        assert mime == "image/jpeg" and Image.open(io.BytesIO(out)).size == (1100, 800)

    def test_missing_pages(self):
        with pytest.raises(tables.PageError):
            tables.page_image(pdf((300, 200)), "application/pdf", 2)
        with pytest.raises(tables.PageError):
            tables.page_image(jpeg(), "image/jpeg", 2)

    def test_tiff_pages(self):
        buf = io.BytesIO()
        frames = [Image.new("L", (300, 200), 255), Image.new("1", (320, 240), 1)]
        frames[0].save(buf, "TIFF", save_all=True, append_images=frames[1:])
        data = buf.getvalue()
        assert tables.page_count(data, "image/tiff") == 2
        out, mime = tables.page_bytes(data, "image/tiff", 2)
        assert mime == "image/jpeg" and Image.open(io.BytesIO(out)).size == (320, 240)

    def test_exif_orientation_is_applied(self):
        exif = Image.Exif()
        exif[0x0112] = 6
        img = tables.page_image(jpeg(400, 300, exif=exif.tobytes()), "image/jpeg", 1)
        assert img.size == (300, 400)

    def test_kinds_and_versions(self):
        assert tables.source_kind({"mime_type": "image/jpeg"}) == "original"
        assert tables.source_kind({"mime_type": "image/heic", "archived_file_name": "a.pdf"}) == "archive"
        assert tables.source_kind({"mime_type": "text/plain", "archived_file_name": None}) is None
        doc = {"modified": "2026-09-01", "versions": [{"checksum": "a"}]}
        assert tables.version_key(doc) != tables.version_key({**doc, "versions": [{"checksum": "b"}]})


class FakePaperless:
    def __init__(self, data, mime):
        self.data, self.mime = data, mime
        self.downloads = 0

    async def download_original(self, doc_id):
        self.downloads += 1
        return self.data, self.mime

    async def download_archive(self, doc_id):
        raise AssertionError("archive not expected")


def test_sources_and_pages_are_cached():
    p = FakePaperless(pdf((300, 200), (300, 200)), "application/pdf")
    doc = {"id": 3, "mime_type": "application/pdf", "page_count": None, "modified": "m"}

    async def go():
        assert await tables.pages(p, doc) == 2
        await tables.page_file(p, doc, 1)
        await tables.page_file(p, doc, 2)
        await tables.page_file(p, doc, 1)
    asyncio.run(go())
    assert p.downloads == 1


class TestTranscription:
    def test_bands_skip_full_rows_and_split_long_runs(self, monkeypatch):
        monkeypatch.setattr(tables, "BAND_ROWS", 3)
        g = grid(ncols=1, nrows=8, cells={"r2": {"c0": "x"}})
        assert tables.bands(g, None) == [(0, 2), (3, 6), (6, 8)]
        assert tables.bands(g, ["r1", "r2", "r3", "r7"]) == [(1, 2), (3, 4), (7, 8)]

    def test_parse_band_matches_lines_by_number(self):
        g = grid(ncols=2, nrows=4, first_line=11)
        answer = {"lines": [
            {"line": "Line 12", "c1": " Anders ", "c2": ""},
            {"line": "013", "c1": "Maria", "c2": "Wife"},
            {"line": "14", "c1": "outside the band"},
            {"line": "?", "c1": "no number"},
        ]}
        assert tables.parse_band(answer, g, 1, 3) == {
            "r1": {"c0": "Anders"}, "r2": {"c0": "Maria", "c1": "Wife"}}

    def test_merge_fills_only_empty_cells_that_still_exist(self):
        g = grid(ncols=2, nrows=2, cells={"r0": {"c0": "typed"}})
        merged, filled = tables.merge_readings(g, {
            "r0": {"c0": "read", "c1": "Head"}, "r1": {"c9": "x"}, "gone": {"c0": "y"}})
        assert filled == 1
        assert merged["cells"] == {"r0": {"c0": "typed", "c1": "Head"}}

    def test_band_image_adds_margins_for_the_labels(self):
        img = Image.new("RGB", (1000, 800), (230, 220, 190))
        out = Image.open(io.BytesIO(tables.band_image(img, grid(nrows=4), 0, 2)))
        assert out.width > 800 and 240 < out.height < 800

    def test_transcribe_reads_each_band_and_reports_one_shared_error(self, monkeypatch):
        monkeypatch.setattr(tables, "BAND_ROWS", 2)
        img = Image.new("RGB", (600, 400), (230, 220, 190))
        g = grid(ncols=2, nrows=4)

        class Gemini:
            def __init__(self, fail=None):
                self.prompts, self.fail = [], fail

            async def generate_json(self, files, prompt, schema, thinking_budget):
                self.prompts.append(prompt)
                assert files[0][1] == "image/jpeg"
                assert schema["properties"]["lines"]["items"]["required"] == ["line", "c1", "c2"]
                if self.fail:
                    raise GeminiError(self.fail)
                first = 1 if "lines 1 to 2" in prompt else 3
                return {"lines": [{"line": str(first + i), "c1": f"name {first + i}", "c2": ""}
                                  for i in range(2)]}

        ok = Gemini()
        readings, errors = asyncio.run(tables.transcribe(ok, img, g, None))
        assert errors == [] and len(ok.prompts) == 2
        assert readings == {f"r{j}": {"c0": f"name {j + 1}"} for j in range(4)}
        assert "c1: Col 0" in ok.prompts[0]

        readings, errors = asyncio.run(tables.transcribe(Gemini("400: API key not valid"), img, g, None))
        assert readings == {} and errors == ["400: API key not valid"]


class TestPeople:
    def test_every_word_of_a_census_name_must_match(self):
        assert tables.people_rules("Lindqvist, Anders") == {"function": "and", "rules": [
            {"name": "SearchName", "values": ["Lindqvist"]}, {"name": "SearchName", "values": ["Anders"]}]}

    def test_initials_are_dropped_unless_alone(self):
        rules = tables.people_rules("A. Lindqvist")["rules"]
        assert [r["values"] for r in rules] == [["Lindqvist"]]
        assert tables.people_rules("A")["rules"] == [{"name": "SearchName", "values": ["A"]}]

    def test_an_id_also_matches_gramps_ids(self):
        rules = tables.people_rules(" I9003 ")
        assert rules["function"] == "or"
        assert {r["name"] for r in rules["rules"]} == {"SearchName", "RegExpIdOf"}

    def test_empty_queries_have_no_rules(self):
        assert tables.people_rules("----- ,") is None

    def test_person_summary_puts_the_given_name_first(self):
        person = {"handle": "h1", "gramps_id": "I9002", "media_list": [{"ref": "m1"}], "profile": {
            "name_display": "Lindqvist, Maria", "name_given": "Maria", "name_surname": "Lindqvist",
            "name_suffix": "", "birth": {"date": "1872-07-07", "place_name": "Vimmerby"},
            "death": {"date": "1955-01-19"}}}
        assert tables.person_summary(person) == {
            "handle": "h1", "gramps_id": "I9002", "name": "Maria Lindqvist", "birth": "1872-07-07",
            "death": "1955-01-19", "photo": True}
        bare = tables.person_summary({"handle": "h2", "gramps_id": "I1", "profile": {"name_display": "X, Y"}})
        assert (bare["name"], bare["photo"], bare["birth"]) == ("X, Y", False, "")
        assert tables.person_summary({"handle": "h3", "gramps_id": "I3"})["name"] == "I3"

    def test_people_columns_are_flagged_only_when_set(self):
        raw = grid()
        raw["cols"][1]["person"] = True
        raw["cols"][2]["person"] = "yes"
        cols = tables.normalize_grid(raw)["cols"]
        assert [c.get("person") for c in cols] == [None, True, None]


class TestAddresses:
    @pytest.mark.parametrize("text,expected", [
        ("69T5AU.L2.C6", ("69T5AU", 1, 2, 2, 6)),
        (" 69t5au.p2.l14 ", ("69T5AU", 2, 14, 14, None)),
        ("69T5AU.L5-1", ("69T5AU", 1, 1, 5, None)),
        ("69T5AU.C12", ("69T5AU", 1, None, None, 12)),
        ("69T5AU", ("69T5AU", 1, None, None, None)),
    ])
    def test_parse(self, text, expected):
        a = tables.parse_address(text)
        assert (a["code"], a["page"], a["line"], a["last"], a["col"]) == expected

    @pytest.mark.parametrize("text", ["", "69T5AU.X1", "69T5AU.C0", "69T5AU..L2", "69T5AU.L2.P1", "SIX"])
    def test_not_addresses(self, text):
        assert tables.parse_address(text) is None

    def test_fragments_mirror_the_suffix(self):
        assert tables.address_fragment(tables.parse_address("69T5AU.P2.L1-5")) == "L1-5"
        assert tables.address_fragment(tables.parse_address("69T5AU.L14.C6")) == "L14.C6"
        assert tables.address_fragment(tables.parse_address("69T5AU.C6")) == "C6"
        assert tables.address_fragment(tables.parse_address("69T5AU")) == ""

    def test_columns_keep_printed_numbers(self):
        raw = grid()
        raw["cols"][1]["no"] = 12
        raw["cols"][2]["no"] = True
        assert [c.get("no") for c in tables.normalize_grid(raw)["cols"]] == [None, 12, None]

    def test_find_doc_asks_paperless_then_the_register(self, conn):
        class Paperless:
            def __init__(self, hits):
                self.hits, self.asked = hits, []

            async def documents_with_value(self, field_id, value):
                self.asked.append((field_id, value))
                return self.hits

        with conn:
            conn.execute("INSERT INTO minted_media (gramps_id, source_system, source_id, minted_at)"
                         " VALUES ('69T5AU', 'paperless', '8', 'now')")
        hit = Paperless([42])
        assert asyncio.run(tables.find_doc(hit, conn, 1, "69T5AU")) == 42
        assert hit.asked == [(1, "69T5AU")]
        assert asyncio.run(tables.find_doc(Paperless([]), conn, 1, "69T5AU")) == 8
        assert asyncio.run(tables.find_doc(Paperless([]), conn, 0, "ZZZZZZ")) is None
