"""Unit tests for the pure sync logic ported from immich_to_gramps.py."""

from bifrost.modules.sync_immich import (
    build_gramps_date,
    find_closest_place,
    format_gramps_date,
    parse_gramps_coord,
    translate_path,
)

MAPPINGS = (
    {"immich_prefix": "/usr/src/app/upload/upload/", "gramps_prefix": "immich/"},
    {"immich_prefix": "/mnt/archive/", "gramps_prefix": "archive/"},
)


def test_translate_path_mappings():
    assert translate_path("/usr/src/app/upload/upload/2026/04/p.jpg", MAPPINGS) \
        == "immich/2026/04/p.jpg"
    assert translate_path("/mnt/archive/box1/scan.tif", MAPPINGS) == "archive/box1/scan.tif"


def test_translate_path_fallback_filename_only():
    assert translate_path("/somewhere/else/photo.jpg", MAPPINGS) == "immich/photo.jpg"


def _asset(tags=(), dt="1955-06-17T10:00:00Z"):
    return {
        "exifInfo": {"dateTimeOriginal": dt},
        "tags": [{"value": t} for t in tags],
    }


def test_date_plain():
    d = build_gramps_date(_asset())
    assert d["dateval"] == [17, 6, 1955, False]
    assert d["modifier"] == 0 and d["quality"] == 0
    assert format_gramps_date(d) == "1955-06-17"


def test_date_approximate_strips_day():
    d = build_gramps_date(_asset(tags=["Date/Approximate"]))
    assert d["dateval"] == [0, 6, 1955, False]
    assert d["modifier"] == 3  # ABOUT
    assert format_gramps_date(d) == "About 1955-06"


def test_date_qualifier_groups_stack():
    d = build_gramps_date(_asset(tags=["Date/Before", "Date/Estimated", "Date/Year"]))
    assert d["dateval"] == [0, 0, 1955, False]
    assert d["modifier"] == 1 and d["quality"] == 1
    assert format_gramps_date(d) == "Est. Before 1955"


def test_date_month_precision():
    d = build_gramps_date(_asset(tags=["Date/Month", "Date/Calculated"]))
    assert d["dateval"] == [0, 6, 1955, False]
    assert d["quality"] == 2
    assert format_gramps_date(d) == "Calc. 1955-06"


def test_date_missing():
    assert build_gramps_date({"exifInfo": {}, "tags": []}) is None


def test_parse_gramps_coord():
    assert parse_gramps_coord("45.5") == 45.5
    assert parse_gramps_coord("N45.5") == 45.5
    assert parse_gramps_coord("W92.9") == -92.9
    assert parse_gramps_coord("S10") == -10.0
    assert parse_gramps_coord("") is None
    assert parse_gramps_coord("garbage") is None


def test_find_closest_place_within_250m():
    near = {"lat": "45.0001", "long": "-92.0001", "name": {"value": "Near"}}
    far = {"lat": "45.1", "long": "-92.1", "name": {"value": "Far"}}
    result = find_closest_place(45.0, -92.0, [far, near])
    assert result is not None
    place, dist = result
    assert place["name"]["value"] == "Near"
    assert dist < 0.25


def test_find_closest_place_none_beyond_250m():
    far = {"lat": "45.1", "long": "-92.1", "name": {"value": "Far"}}
    assert find_closest_place(45.0, -92.0, [far]) is None
