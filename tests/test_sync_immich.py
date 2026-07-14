"""Unit tests for the single-asset Immich sync's pure helpers."""

import pytest

from bifrost.modules.sync_immich import (
    SyncError,
    gda_date_to_gramps,
    load_person_map,
    translate_path,
)

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


class TestGdaDateToGramps:
    def test_about_year_only(self):
        d = gda_date_to_gramps(
            {"modifier": "about", "quality": "estimated", "start": {"year": 1920, "month": 0, "day": 0}}
        )
        assert d == {
            "_class": "Date",
            "dateval": [0, 0, 1920, False],
            "modifier": 3,
            "quality": 1,
            "text": "",
        }

    def test_exact_date_defaults(self):
        d = gda_date_to_gramps({"start": {"year": 1955, "month": 7, "day": 14}})
        assert d["dateval"] == [14, 7, 1955, False]
        assert d["modifier"] == 0
        assert d["quality"] == 0

    def test_range_is_eight_element_dateval(self):
        d = gda_date_to_gramps(
            {"modifier": "range", "start": {"year": 1920}, "stop": {"year": 1929, "month": 12}}
        )
        assert d["dateval"] == [0, 0, 1920, False, 0, 12, 1929, False]
        assert d["modifier"] == 4

    def test_textonly(self):
        d = gda_date_to_gramps({"modifier": "textonly", "text": "wedding day"})
        assert d["dateval"] == [0, 0, 0, False]
        assert d["modifier"] == 6
        assert d["text"] == "wedding day"

    def test_unknown_modifier_rejected(self):
        with pytest.raises(SyncError):
            gda_date_to_gramps({"modifier": "sometime", "start": {"year": 1920}})


class TestLoadPersonMap:
    def test_missing_file_is_empty(self, tmp_path):
        assert load_person_map(tmp_path / "nope.yaml") == {}
        assert load_person_map(None) == {}

    def test_parses_face_linker_shape(self, tmp_path):
        p = tmp_path / "person_map.yaml"
        p.write_text(
            "people:\n"
            "- gramps_handle: abc123\n"
            "  immich_person_id: uuid-1\n"
            "  label: Ed Grund\n"
            "- gramps_handle: def456\n"
            "  immich_person_id: uuid-2\n"
        )
        m = load_person_map(p)
        assert m["uuid-1"] == {"handle": "abc123", "label": "Ed Grund"}
        assert m["uuid-2"]["label"] == ""
