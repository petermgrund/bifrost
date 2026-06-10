"""Unit tests for the gnarly pure logic ported from the legacy monolith."""

import sqlite3

import yaml

from bifrost.core import db
from bifrost.modules.faces import (
    delete_link,
    export_person_map,
    immich_face_to_gramps_rect,
    list_links,
    person_map_dict,
    set_link,
)

FACE = {
    "imageWidth": 1000, "imageHeight": 500,
    "boundingBoxX1": 100, "boundingBoxY1": 50,
    "boundingBoxX2": 300, "boundingBoxY2": 150,
}


def test_rect_tight():
    assert immich_face_to_gramps_rect(FACE, pad_factor=0.0) == [10, 10, 30, 30]


def test_rect_padded():
    # bw=200, bh=100; each side grows by 15% of box dimension
    assert immich_face_to_gramps_rect(FACE, pad_factor=0.15) == [7, 7, 33, 33]


def test_rect_clamps_to_bounds():
    face = {**FACE, "boundingBoxX1": 10, "boundingBoxY1": 5,
            "boundingBoxX2": 990, "boundingBoxY2": 495}
    assert immich_face_to_gramps_rect(face, pad_factor=0.15) == [0, 0, 100, 100]


def test_rect_missing_dimensions():
    assert immich_face_to_gramps_rect({"boundingBoxX1": 1}) is None
    assert immich_face_to_gramps_rect({**FACE, "imageWidth": 0}) is None


def _conn(tmp_path) -> sqlite3.Connection:
    return db.connect(tmp_path / "t.db")


def test_link_semantics(tmp_path):
    conn = _conn(tmp_path)
    set_link(conn, "H1", "I1", "Grandma", None)
    set_link(conn, "H2", "I2", None, None)
    # Legacy semantics: one Immich person per Gramps handle — relink replaces
    set_link(conn, "H1", "I9", "Grandma!", None)
    links = list_links(conn)
    assert links == [
        {"gramps_handle": "H2", "immich_person_id": "I2"},
        {"gramps_handle": "H1", "immich_person_id": "I9", "label": "Grandma!"},
    ]
    assert person_map_dict(conn) == {"I2": "H2", "I9": "H1"}
    assert delete_link(conn, "H2", None) is True
    assert delete_link(conn, "H2", None) is False


def test_yaml_export_matches_legacy_format(tmp_path):
    conn = _conn(tmp_path)
    set_link(conn, "H1", "I1", "Grandma", None)
    set_link(conn, "H2", "I2", None, None)
    out = tmp_path / "person_map.yaml"
    export_person_map(conn, out)
    text = out.read_text()
    assert text.startswith("# Person mapping")
    data = yaml.safe_load(text)
    assert data == {"people": [
        {"gramps_handle": "H1", "immich_person_id": "I1", "label": "Grandma"},
        {"gramps_handle": "H2", "immich_person_id": "I2"},
    ]}
