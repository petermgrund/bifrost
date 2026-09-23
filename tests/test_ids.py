import sqlite3

import pytest

from bifrost.core import db, ids

# XJ4DBT stands for a minted id whose media was later deleted from Gramps
GONE = "XJ4DBT"


def seed(conn):
    conn.execute(
        "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
        "VALUES (?, 'paperless', '101', 'Deleted doc', '2026-01-01')", (GONE,))
    conn.executemany(
        "INSERT INTO reserved_ids (gramps_id, created_at, assigned_at, minted_at) VALUES (?, 't', ?, ?)",
        [("PENCHD", None, None), ("RSVD22", "t", None), ("MNTD22", "t", "t")])
    conn.execute("INSERT INTO scan_register (scan_no, object_id) VALUES ('a000001', 'SCAN22')")
    conn.commit()


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    seed(c)
    yield c
    c.close()


def test_all_ids_ever_seen_unions_every_source(conn):
    seen = ids.all_ids_ever_seen(conn, {"LIVE22"}, [" ppr222 ", None, ""])
    assert {GONE, "PENCHD", "RSVD22", "MNTD22", "SCAN22", "LIVE22", "PPR222"} <= seen
    assert ids.LEGACY_IDS <= seen
    assert "" not in seen and None not in seen


def test_open_reservations_stay_claimable_for_manual_ids(conn):
    seen = ids.all_ids_ever_seen(conn, open_reservations=False)
    assert {"PENCHD", "RSVD22"} & seen == set()
    assert {GONE, "MNTD22", "SCAN22"} <= seen


def test_generator_never_reissues_a_seen_id(conn, script_ids):
    script_ids(GONE, "PENCHD", "RSVD22", "MNTD22", "SCAN22", "FRESH2")
    assert ids.generate_gramps_id(ids.all_ids_ever_seen(conn)) == "FRESH2"


def test_register_conflict_raises_and_keeps_the_row(conn):
    with pytest.raises(ids.IdReused, match="paperless 101"):
        ids.register_minted(conn, GONE, "immich", "a1", "New photo", "2026-09-22")
    row = conn.execute(
        "SELECT source_system, source_id, title FROM minted_media WHERE gramps_id=?",
        (GONE,)).fetchone()
    assert tuple(row) == ("paperless", "101", "Deleted doc")
    assert issubclass(ids.IdReused, sqlite3.IntegrityError)


def test_register_other_integrity_errors_propagate(conn):
    with pytest.raises(sqlite3.IntegrityError) as exc:
        ids.register_minted(conn, "FRESH2", "flickr", "x", None, "2026-09-22")
    assert not isinstance(exc.value, ids.IdReused)
