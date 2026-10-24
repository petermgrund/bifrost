import sqlite3

import pytest

from bifrost.core import db, ids

# XJ4DBT stands for a minted id whose media was later deleted from Gramps
GONE = "XJ4DBT"
RETIRED = {"C8T5", "J82D", "JYMZ", "6H2P", "G8NQ"}


def seed(conn):
    conn.execute(
        "INSERT INTO minted_media (gramps_id, source_system, source_id, created_at, minted_at) "
        "VALUES (?, 'paperless', '101', '2026-01-01', '2026-01-01')", (GONE,))
    conn.executemany(
        "INSERT INTO minted_media (gramps_id, created_at, withdrawn_at, withdrawn_reason) VALUES (?, 't', ?, ?)",
        [("RSVD22", None, None), ("PENCHD", None, None), ("WDRN22", "t", "mistake")])
    conn.commit()


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    seed(c)
    yield c
    c.close()


def test_all_ids_ever_seen_unions_every_source(conn):
    seen = ids.all_ids_ever_seen(conn, {"LIVE22"}, [" ppr222 ", None, ""])
    assert {GONE, "RSVD22", "PENCHD", "WDRN22", "LIVE22", "PPR222"} <= seen
    assert RETIRED <= seen
    assert "" not in seen and None not in seen


def test_open_reservations_stay_claimable_for_manual_ids(conn):
    seen = ids.all_ids_ever_seen(conn, open_reservations=False)
    assert {"RSVD22", "PENCHD"} & seen == set()
    assert {GONE, "WDRN22"} | RETIRED <= seen


def test_generator_never_reissues_a_seen_id(conn, script_ids):
    script_ids(GONE, "RSVD22", "PENCHD", "WDRN22", "FRESH2")
    assert ids.generate_gramps_id(ids.all_ids_ever_seen(conn)) == "FRESH2"


def test_register_adds_a_row_or_takes_the_reservation(conn):
    ids.register_minted(conn, "FRESH2", "immich", "a1", "2026-09-22")
    fresh = conn.execute("SELECT * FROM minted_media WHERE gramps_id='FRESH2'").fetchone()
    assert (fresh["source_system"], fresh["source_id"]) == ("immich", "a1")
    assert fresh["created_at"] == fresh["minted_at"] == "2026-09-22"
    ids.register_minted(conn, "RSVD22", "paperless", "7", "2026-09-23")
    taken = conn.execute("SELECT * FROM minted_media WHERE gramps_id='RSVD22'").fetchone()
    assert (taken["source_system"], taken["source_id"], taken["created_at"], taken["minted_at"]) == (
        "paperless", "7", "t", "2026-09-23")
    assert "RSVD22" in ids.all_ids_ever_seen(conn, open_reservations=False)


@pytest.mark.parametrize("code,msg", [(GONE, "paperless 101"), ("WDRN22", "withdrawn on t")])
def test_register_conflict_raises_and_keeps_the_row(conn, code, msg):
    before = tuple(conn.execute("SELECT * FROM minted_media WHERE gramps_id=?", (code,)).fetchone())
    with pytest.raises(ids.IdReused, match=msg):
        ids.register_minted(conn, code, "immich", "a1", "2026-09-22")
    assert tuple(conn.execute("SELECT * FROM minted_media WHERE gramps_id=?", (code,)).fetchone()) == before
    assert issubclass(ids.IdReused, sqlite3.IntegrityError)


def test_register_other_integrity_errors_propagate(conn):
    with pytest.raises(sqlite3.IntegrityError) as exc:
        ids.register_minted(conn, "FRESH2", "flickr", "x", "2026-09-22")
    assert not isinstance(exc.value, ids.IdReused)


def test_next_sequential_id():
    assert ids.next_sequential_id("C", {"C0001", "C0036", "C0068"}) == "C0069"
    assert ids.next_sequential_id("N", {"N0134", "N_XNH8SH", "N_RX4ZRR"}) == "N0135"
    assert ids.next_sequential_id("R", set()) == "R0001"
    assert ids.next_sequential_id("C", {"C9999"}) == "C10000"
