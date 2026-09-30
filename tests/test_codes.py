import asyncio
import csv
import io
import re
import sqlite3
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core import db, ids
from bifrost.core.clients.gramps import GrampsError
from bifrost.core.clients.paperless import PaperlessClient, PaperlessError
from bifrost.core.config import SyncImmichConfig, SyncPaperlessConfig
from bifrost.modules import codes, sync_immich
from bifrost.modules.sync_immich import SyncError
from bifrost.web.routes import codes as codes_routes
from test_sync_immich import CFG, FakeGramps, FakeImmich, asset, summary_of

# GONE: minted, then its media was deleted from Gramps; MNTD22: minted and live
GONE, MNTD22 = "XJ4DBT", "MNTD22"
URLS = codes.Urls(gramps="https://gramps.example", paperless="https://docs.example",
                  immich="https://img.example")


def seed(conn):
    conn.executemany(
        "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [(GONE, "paperless", "101", "Deleted doc", "2026-01-01T10:00:00"),
         (MNTD22, "immich", "asset-1", "Mario's First Communion", "2026-02-01T10:00:00")])
    conn.executemany(
        "INSERT INTO reserved_ids (gramps_id, created_at, note) VALUES (?, ?, ?)",
        [("RSVD22", "2026-03-01T10:00:00", "Reserved, not written yet"),
         ("PENCHD", "2026-03-02T10:00:00", "Penciled print")])
    conn.execute("INSERT INTO code_pencilings (code, penciled_at) "
                 "VALUES ('PENCHD', '2026-03-03T10:00:00')")
    conn.execute("INSERT INTO scan_register (scan_no, object_id) VALUES ('a000277', 'SCAN22')")
    conn.execute(
        "INSERT INTO doc_versions (paperless_id, checksum, gramps_id, updated_at) "
        "VALUES (99, 'c', ?, 't')", (GONE,))
    conn.commit()


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    seed(c)
    yield c
    c.close()


def by_code(conn, live=frozenset({MNTD22})):
    return {r["code"]: r for r in codes.rows(conn, None if live is None else set(live), URLS)}


def group(conn, note="Johnny Gillio's photographs", location="B3"):
    return codes.mint(conn, kind="group", note=note, location=location)[0]


# ---- migration 15, the withdrawn register and the guards

def test_migration_seeds_the_retired_codes(conn):
    rows = conn.execute("SELECT code, withdrawn_at, reason FROM withdrawn_codes").fetchall()
    assert {r["code"] for r in rows} == ids.LEGACY_IDS
    assert all(r["withdrawn_at"] and "4-character" in r["reason"] for r in rows)
    assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == len(db.MIGRATIONS)


def test_objects_kind_is_item_or_group(conn):
    conn.execute("INSERT INTO objects (object_id) VALUES ('KIND22')")
    assert conn.execute("SELECT kind FROM objects WHERE object_id='KIND22'").fetchone()[0] == "item"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO objects (object_id, kind) VALUES ('KIND23', 'album')")


def test_withdrawn_table_is_the_authority(conn):
    conn.execute("INSERT INTO withdrawn_codes (code, withdrawn_at, reason) VALUES ('WDRN22', 't', 'test')")
    assert "WDRN22" in ids.all_ids_ever_seen(conn)
    assert ids.LEGACY_IDS <= ids.all_ids_ever_seen(conn)
    # the constant is only the seed: the table decides
    conn.execute("DELETE FROM withdrawn_codes WHERE code='C8T5'")
    assert "C8T5" not in ids.all_ids_ever_seen(conn)


@pytest.mark.parametrize("code,why", [
    ("222222", "all digits"), ("234567", "all digits"),
    ("B2C3F4", "location mark B2.C3.F4"), ("B23456", "location mark B23456"),
    ("S2C3F4", "location mark S2.C3.F4"), ("B2C345", "location mark B2.C345"),
    ("S1", "location mark S1"), ("B99F22", "location mark B99.F22"),
    ("README", "reserved word"), ("SCHEME", "reserved word"),
])
def test_guarded_shapes(code, why):
    assert why in ids.guard_reason(code)


# the B/S-plus-digit ids that live in the ledger today
@pytest.mark.parametrize("code", ["B36Z55", "B2YQHE", "B446TP", "B5KU2X", "B74XFT", "B788RV",
                                  "B9U4GF", "S4WVRG", "S7HP82", "BC2345", "PHKN3D", "XFETYZ"])
def test_real_ids_pass_the_guards(code):
    assert ids.guard_reason(code) is None


def test_generator_skips_guarded_candidates(script_ids):
    script_ids("222222", "B2C3F4", "README", "SCHEME", "FRESH2")
    assert ids.generate_gramps_id(set()) == "FRESH2"


def test_open_reservation_with_a_scan_stays_claimable(conn):
    conn.execute("INSERT INTO reserved_ids (gramps_id, created_at) VALUES ('PHKN3D', 't')")
    conn.execute("INSERT INTO scan_register (scan_no, object_id) VALUES ('a000278', 'PHKN3D')")
    conn.execute("INSERT INTO objects (object_id) VALUES ('RSVD22')")
    conn.execute("INSERT INTO withdrawn_codes (code, withdrawn_at, reason) VALUES ('PENCHD', 't', 'mistake')")
    claimable = ids.all_ids_ever_seen(conn, open_reservations=False)
    assert {"PHKN3D", "RSVD22"} & claimable == set()
    assert {"PENCHD", "SCAN22", GONE} <= claimable
    assert {"PHKN3D", "RSVD22", "PENCHD"} <= ids.all_ids_ever_seen(conn)


# ---- minting

def test_mint_never_returns_a_used_withdrawn_or_guarded_code(conn, script_ids):
    conn.execute("INSERT INTO withdrawn_codes (code, withdrawn_at, reason) VALUES ('WDRN22', 't', 'test')")
    conn.execute("INSERT INTO objects (object_id) VALUES ('DESC22')")
    script_ids(GONE, MNTD22, "RSVD22", "PENCHD", "SCAN22", "WDRN22", "DESC22", "GRMP22",
               "PPR222", "222222", "B2C3F4", "README", "FRESH2", "FRESH3")
    new = codes.mint(conn, kind="item", note="Loose print", count=2,
                     live={"GRMP22"}, paperless={"PPR222"})
    assert new == ["FRESH2", "FRESH3"]


def test_mint_writes_a_reservation_and_a_description(conn):
    g = group(conn)
    new = codes.mint(conn, kind="item", note="  Mario's  portrait ", parent=g.lower(),
                     location="b3 c1", count=3)
    assert len(set(new)) == 3 and all(ids.MANUAL_ID_RE.match(c) for c in new)
    for code in new:
        res = conn.execute("SELECT * FROM reserved_ids WHERE gramps_id=?", (code,)).fetchone()
        assert res["created_at"] and res["note"] == "Mario's portrait"
        assert res["assigned_at"] is None and res["minted_at"] is None
        obj = conn.execute("SELECT * FROM objects WHERE object_id=?", (code,)).fetchone()
        assert (obj["kind"], obj["parent_id"], obj["location"], obj["note"]) == (
            "item", g, "B3.C1", "Mario's portrait")
    assert by_code(conn)[g]["children"] == 3


def test_mint_and_claim_without_a_description(conn, script_ids):
    script_ids("FRESH2", "FRESH3", "FRESH4")
    assert codes.mint(conn, kind="item", note="  ", count=3) == ["FRESH2", "FRESH3", "FRESH4"]
    assert codes.claim(conn, "FRESH5", kind="item", note=None) == "FRESH5"
    rows = by_code(conn)
    for code in ("FRESH2", "FRESH3", "FRESH4", "FRESH5"):
        assert (rows[code]["status"], rows[code]["note"]) == ("reserved", None)
        assert rows[code]["history"] == [
            {"at": rows[code]["created"], "what": "Created", "detail": None}]


@pytest.mark.parametrize("kw,msg", [
    ({"kind": "album"}, "item or group"),
    ({"count": 0}, "between 1 and 20"),
    ({"count": 21}, "between 1 and 20"),
    ({"parent": "NOPE22"}, "not in the ledger"),
])
def test_mint_refusals_write_nothing(conn, kw, msg):
    before = conn.execute("SELECT COUNT(*) FROM reserved_ids").fetchone()[0]
    with pytest.raises(codes.CodeError, match=msg) as exc:
        codes.mint(conn, **{"kind": "item", "note": "A print", **kw})
    assert exc.value.status == 400
    assert conn.execute("SELECT COUNT(*) FROM reserved_ids").fetchone()[0] == before
    assert conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0


# ---- claiming a code written by hand

def test_claim_normalizes_and_registers(conn):
    code = codes.claim(conn, " fre-sh 2 ", kind="group", note="Bundle of letters",
                       live={MNTD22}, paperless={})
    assert code == "FRESH2"
    row = by_code(conn)["FRESH2"]
    assert (row["status"], row["kind"], row["note"]) == ("reserved", "group", "Bundle of letters")


@pytest.mark.parametrize("raw,status,msg", [
    ("", 400, "Type the code"),
    ("PHKN0D", 400, "contains 0"),
    ("phkil3", 400, "contains I, L"),
    ("PHKN3", 400, "has 5 characters"),
    ("PHKN3DD", 400, "has 7 characters"),
    ("jymz", 409, "withdrawn on"),
    ("b2c3f4", 400, "location mark B2.C3.F4"),
    ("222 222", 400, "all digits"),
    ("readme", 400, "reserved word"),
    (GONE, 409, "minted from Paperless document 101"),
    (MNTD22, 409, "minted from Immich asset asset-1"),
    ("rsvd22", 409, "reserved since 2026-03-01"),
    ("PENCHD", 409, "penciled since"),
    ("SCAN22", 409, "scan register (a000277)"),
    ("GRMP22", 409, "Gramps media"),
    ("PPR222", 409, "Paperless document 7"),
])
def test_claim_refusals(conn, raw, status, msg):
    with pytest.raises(codes.CodeError, match=re.escape(msg)) as exc:
        codes.claim(conn, raw, kind="item", note="A print", live={"GRMP22"},
                    paperless={"PPR222": [7]})
    assert exc.value.status == status
    assert conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0


# ---- status

def test_status_derivation(conn):
    conn.execute("INSERT INTO reserved_ids (gramps_id, created_at, minted_at) "
                 "VALUES ('MARKED', '2026-04-01T10:00:00', '2026-04-02T10:00:00')")
    rows = by_code(conn, live={MNTD22, "GRMP22", "O0001"})
    assert rows["RSVD22"]["status"] == "reserved"
    assert rows["PENCHD"]["status"] == "penciled"
    assert rows["SCAN22"]["status"] == "reserved"
    assert rows[MNTD22]["status"] == "in use" and rows[MNTD22]["attention"] is None
    assert rows["MARKED"]["status"] == "in use"
    assert rows[GONE]["status"] == "in use"
    assert rows[GONE]["attention"] == "Deleted from Gramps"
    assert rows["GRMP22"]["status"] == "in use" and "not in bifrost's ledger" in rows["GRMP22"]["attention"]
    assert "O0001" not in rows  # a Gramps default id is not a code
    assert rows["JYMZ"]["status"] == "withdrawn"
    assert rows[MNTD22]["gramps_url"] == f"https://gramps.example/media/{MNTD22}"
    assert rows[MNTD22]["immich"] == [{"id": "asset-1", "url": "https://img.example/photos/asset-1"}]
    assert [d["id"] for d in rows[GONE]["paperless"]] == ["101", "99"]
    assert rows[GONE]["gramps_url"] is None


def test_deleted_paperless_documents_drop_out(conn):
    def row(live, documents):
        return {r["code"]: r for r in codes.rows(conn, live, URLS, documents=documents)}[GONE]
    assert [d["id"] for d in row({MNTD22}, {"99"})["paperless"]] == ["99"]
    assert row({MNTD22}, {"99"})["attention"] == "Deleted from Gramps and Paperless"
    assert row({MNTD22, GONE}, {"99"})["attention"] == "Deleted from Paperless"
    assert row({MNTD22, GONE}, {"99", "101"})["attention"] is None
    gone = row({MNTD22, GONE}, set())
    assert gone["paperless"] == [] and [i["where"] for i in gone["instances"]] == ["Gramps"]
    assert row({MNTD22}, None)["attention"] == "Deleted from Gramps"


def test_a_withdrawn_code_does_not_link_its_deleted_document(conn):
    codes.withdraw(conn, GONE, "deleted in gramps and paperless")
    row = {r["code"]: r for r in codes.rows(conn, {MNTD22}, URLS, documents=set())}[GONE]
    assert (row["status"], row["attention"], row["instances"]) == ("withdrawn", None, [])
    assert row["withdrawn_reason"] == "deleted in gramps and paperless"


def test_unknown_gramps_leaves_the_ledger_status(conn):
    rows = by_code(conn, live=None)
    assert rows[GONE]["status"] == "in use"
    assert rows[GONE]["attention"] is None and rows[GONE]["gramps"] is None
    assert rows[MNTD22]["gramps_url"] is None


def test_withdrawn_beats_in_use(conn):
    codes.withdraw(conn, MNTD22, "duplicate of another print")
    row = by_code(conn)[MNTD22]
    assert (row["status"], row["withdrawn_reason"]) == ("withdrawn", "duplicate of another print")
    assert row["attention"] is None


def test_rows_sort_newest_first_and_counts(conn):
    items = codes.rows(conn, {MNTD22}, URLS)
    # newest reservation or mint first; codes with neither last, by code
    assert [r["code"] for r in items] == [
        "PENCHD", "RSVD22", MNTD22, GONE, "6H2P", "C8T5", "G8NQ", "J82D", "JYMZ", "SCAN22"]
    c = codes.counts(items)
    assert c == {"all": 10, "reserved": 2, "penciled": 1, "in use": 2, "withdrawn": 5,
                 "attention": 1}
    assert [r["code"] for r in codes.search(items, "communion")] == [MNTD22]
    assert [r["code"] for r in codes.search(items, "xj4-dbt")] == [GONE]
    assert [r["code"] for r in codes.search(items, "a000277")] == ["SCAN22"]


@pytest.mark.parametrize("raw,wanted", [("", None), ("all", None), ("in_use", "in use"),
                                        ("In-Use", "in use"), ("needs attention", "attention"),
                                        ("withdrawn", "withdrawn")])
def test_status_filter(raw, wanted):
    assert codes.status_filter(raw) == wanted


def test_status_filter_rejects_garbage():
    with pytest.raises(ValueError):
        codes.status_filter("lost")


# ---- penciled, withdraw

def test_penciling_again_adds_an_entry(conn):
    codes.mark_penciled(conn, "rsvd22")
    conn.execute("UPDATE code_pencilings SET penciled_at='2026-05-01T00:00:00' WHERE code='RSVD22'")
    codes.mark_penciled(conn, "RSVD22")
    row = by_code(conn)["RSVD22"]
    assert row["status"] == "penciled"
    assert [(p["n"], p["crossed"]) for p in row["pencilings"]] == [(1, None), (2, None)]
    assert row["pencilings"][0]["at"] == "2026-05-01T00:00:00"
    assert row["penciled"] == row["pencilings"][1]["at"]


def test_penciling_a_code_minted_straight_from_sync(conn):
    codes.mark_penciled(conn, MNTD22)
    assert conn.execute("SELECT 1 FROM reserved_ids WHERE gramps_id=?", (MNTD22,)).fetchone() is None
    row = by_code(conn)[MNTD22]
    assert row["status"] == "in use" and row["penciled"] == row["pencilings"][0]["at"]


def test_crossing_out_one_penciling_leaves_the_others(conn):
    codes.mark_penciled(conn, "RSVD22")
    codes.mark_penciled(conn, "RSVD22")
    first, second = by_code(conn)["RSVD22"]["pencilings"]
    codes.cross_out_penciling(conn, "rsvd22", first["id"])
    row = by_code(conn)["RSVD22"]
    assert row["status"] == "penciled" and row["pencilings"][0]["crossed"]
    assert row["pencilings"][1]["crossed"] is None and row["penciled"] == second["at"]
    assert [e["what"] for e in row["history"]][-3:] == [
        "Penciled #1", "Penciled #2", "Penciling #1 crossed out"]
    codes.cross_out_penciling(conn, "RSVD22", second["id"])
    row = by_code(conn)["RSVD22"]
    assert row["status"] == "reserved" and row["penciled"] is None
    assert conn.execute("SELECT COUNT(*) FROM code_pencilings WHERE code='RSVD22'").fetchone()[0] == 2


def test_cross_out_refusals(conn):
    [p] = by_code(conn)["PENCHD"]["pencilings"]
    for code, pid, status in [("RSVD22", p["id"], 404), ("PENCHD", 999, 404),
                              ("NOPE22", p["id"], 404)]:
        with pytest.raises(codes.CodeError) as exc:
            codes.cross_out_penciling(conn, code, pid)
        assert exc.value.status == status
    codes.withdraw(conn, "PENCHD", "wrong print")
    codes.cross_out_penciling(conn, "PENCHD", p["id"])
    with pytest.raises(codes.CodeError, match="already crossed out") as exc:
        codes.cross_out_penciling(conn, "PENCHD", p["id"])
    assert exc.value.status == 409


def test_migration_18_moves_pencilings(tmp_path):
    path = tmp_path / "v17.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    for number, script in enumerate(db.MIGRATIONS[:17], start=1):
        old.executescript(script)
        old.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
    old.executemany("INSERT INTO reserved_ids (gramps_id, created_at, assigned_at) VALUES (?, ?, ?)",
                    [("PNCL22", "2026-09-01T10:00:00", "2026-09-02T10:00:00"),
                     ("RSVD22", "2026-09-01T10:00:00", None)])
    old.commit()
    old.close()
    conn = db.connect(path)
    assert [tuple(r) for r in conn.execute(
        "SELECT code, penciled_at, crossed_at FROM code_pencilings")] == [
        ("PNCL22", "2026-09-02T10:00:00", None)]
    assert by_code(conn)["PNCL22"]["status"] == "penciled"
    conn.close()


def test_penciled_refusals(conn):
    with pytest.raises(codes.CodeError) as exc:
        codes.mark_penciled(conn, "NOPE22")
    assert exc.value.status == 404
    with pytest.raises(codes.CodeError) as exc:
        codes.mark_penciled(conn, "JYMZ")
    assert exc.value.status == 409
    with pytest.raises(codes.CodeError, match="is a document") as exc:
        codes.mark_penciled(conn, GONE)
    assert exc.value.status == 409
    codes.mark_penciled(conn, MNTD22)


def test_withdraw_blocks_reuse_and_deletes_nothing(conn, script_ids):
    codes.withdraw(conn, "rsvd22", "  penciled on the wrong print ")
    gone = conn.execute("SELECT * FROM withdrawn_codes WHERE code='RSVD22'").fetchone()
    assert gone["reason"] == "penciled on the wrong print" and gone["withdrawn_at"]
    assert conn.execute("SELECT 1 FROM reserved_ids WHERE gramps_id='RSVD22'").fetchone()
    assert by_code(conn)["RSVD22"]["status"] == "withdrawn"
    with pytest.raises(codes.CodeError, match="withdrawn on") as exc:
        codes.claim(conn, "RSVD22", kind="item", note="again")
    assert exc.value.status == 409
    script_ids("RSVD22", "FRESH2")
    assert codes.mint(conn, kind="item", note="new") == ["FRESH2"]
    assert "RSVD22" in ids.all_ids_ever_seen(conn, open_reservations=False)
    with pytest.raises(codes.CodeError, match="already withdrawn") as exc:
        codes.withdraw(conn, "RSVD22", "twice")
    assert exc.value.status == 409


@pytest.mark.parametrize("code,reason,status", [
    ("RSVD22", " ", 400), ("NOPE22", "gone", 404)])
def test_withdraw_refusals(conn, code, reason, status):
    with pytest.raises(codes.CodeError) as exc:
        codes.withdraw(conn, code, reason)
    assert exc.value.status == status
    assert conn.execute("SELECT COUNT(*) FROM withdrawn_codes").fetchone()[0] == 5


# ---- describing: kind, note, part of, location

def test_update_only_changes_given_fields(conn):
    codes.update(conn, "RSVD22", {"location": "b2c3f1"})
    obj = conn.execute("SELECT * FROM objects WHERE object_id='RSVD22'").fetchone()
    # the reservation's note carries over into the new description
    assert (obj["kind"], obj["note"], obj["location"]) == ("item", "Reserved, not written yet", "B2.C3.F1")
    codes.update(conn, "RSVD22", {"note": "Loose print, Gillio box"})
    obj = conn.execute("SELECT * FROM objects WHERE object_id='RSVD22'").fetchone()
    assert (obj["note"], obj["location"]) == ("Loose print, Gillio box", "B2.C3.F1")
    codes.update(conn, "RSVD22", {"location": None})
    assert conn.execute("SELECT location FROM objects WHERE object_id='RSVD22'").fetchone()[0] is None
    # the reservation itself is history and stays as it was
    assert conn.execute("SELECT note FROM reserved_ids WHERE gramps_id='RSVD22'"
                        ).fetchone()[0] == "Reserved, not written yet"
    with pytest.raises(codes.CodeError) as exc:
        codes.update(conn, "NOPE22", {"note": "x"})
    assert exc.value.status == 404


def test_parent_rules(conn):
    g = group(conn)
    item = codes.mint(conn, kind="item", note="Loose print")[0]
    codes.update(conn, "RSVD22", {"parent": g})
    assert by_code(conn)["RSVD22"]["parent"] == g
    for parent, msg in [(item, "not a group"), ("RSVD22", "not a group"), ("NOPE22", "not in the ledger"),
                        ("JYMZ", "withdrawn")]:
        with pytest.raises(codes.CodeError, match=msg):
            codes.update(conn, "PENCHD", {"parent": parent})
    with pytest.raises(codes.CodeError, match="part of itself"):
        codes.update(conn, g, {"parent": g})
    inner = codes.mint(conn, kind="group", note="Envelope", parent=g)[0]
    with pytest.raises(codes.CodeError, match="already part of"):
        codes.update(conn, g, {"parent": inner})
    with pytest.raises(codes.CodeError, match="under it") as exc:
        codes.update(conn, g, {"kind": "item"})
    assert exc.value.status == 409
    codes.update(conn, "RSVD22", {"parent": None})
    assert by_code(conn)["RSVD22"]["parent"] is None


# ---- history and the digital record's description

def test_history_is_chronological(conn):
    codes.update(conn, "PENCHD", {"note": "Penciled print, Gillio box"})
    codes.withdraw(conn, "PENCHD", "wrong print")
    row = by_code(conn)["PENCHD"]
    assert [(e["what"], e["detail"]) for e in row["history"]] == [
        ("Created", "Penciled print"), ("Penciled #1", None),
        ("Description changed", "Penciled print, Gillio box"), ("Withdrawn", "wrong print")]
    assert row["history"][0]["at"] == "2026-03-02T10:00:00"
    assert row["updated"] == row["history"][-1]["at"]


def test_history_of_codes_minted_by_sync(conn):
    codes.mark_penciled(conn, MNTD22)
    rows = by_code(conn)
    assert [e["what"] for e in rows[MNTD22]["history"]] == ["Minted from Immich", "Penciled #1"]
    assert [e["what"] for e in rows[GONE]["history"]] == ["Minted from Paperless document 101"]
    assert rows["SCAN22"]["history"] == [] and rows["SCAN22"]["updated"] is None


def test_digital_records_own_their_description(conn):
    conn.execute("INSERT INTO doc_versions (paperless_id, checksum, gramps_id, updated_at) "
                 "VALUES (98, 'c', 'RSVD22', 't')")
    for code, where in [(MNTD22, "Immich"), (GONE, "Paperless document 101"),
                        ("RSVD22", "Paperless document 98")]:
        with pytest.raises(codes.CodeError, match=f"described in {where}") as exc:
            codes.update(conn, code, {"note": "My own words"})
        assert exc.value.status == 409
    codes.update(conn, MNTD22, {"note": ""})
    assert conn.execute("SELECT COUNT(*) FROM code_descriptions").fetchone()[0] == 0


def test_title_comes_from_gramps_when_it_answers(conn):
    live = {r["code"]: r for r in codes.rows(
        conn, {MNTD22}, URLS, titles={MNTD22: "Mario, First Communion 1952"})}
    assert live[MNTD22]["title"] == "Mario, First Communion 1952"
    assert by_code(conn)[MNTD22]["title"] == "Mario's First Communion"


def test_type_and_instances_of_digital_codes(conn):
    rows = by_code(conn)
    assert (rows[MNTD22]["type"], rows[GONE]["type"], rows["RSVD22"]["type"]) == (
        "image", "document", None)
    assert [(i["where"], i["text"], i["url"]) for i in rows[MNTD22]["instances"]] == [
        ("Immich", "Asset asset-1", "https://img.example/photos/asset-1"),
        ("Gramps", f"Media {MNTD22}", f"https://gramps.example/media/{MNTD22}")]
    assert [(i["where"], i["text"]) for i in rows[GONE]["instances"]] == [
        ("Paperless", "Document 101"), ("Paperless", "Document 99")]
    assert [(i["where"], i["text"]) for i in rows["SCAN22"]["instances"]] == [("Scan", "a000277")]


def test_links_added_by_hand(conn):
    first = "https://www.familysearch.org/ark:/61903/3:1:X"
    second = "https://www.ancestry.com/sharing/123"
    codes.add_instance(conn, "rsvd22", f"  {first} ")
    codes.add_instance(conn, "RSVD22", second)
    row = by_code(conn)["RSVD22"]
    assert [(i["where"], i["text"], i["url"]) for i in row["instances"]] == [
        ("Link", first, first), ("Link", second, second)]
    assert [r["code"] for r in codes.search(list(by_code(conn).values()), "ancestry")] == ["RSVD22"]
    codes.remove_instance(conn, "RSVD22", row["instances"][1]["id"])
    row = by_code(conn)["RSVD22"]
    assert [i["text"] for i in row["instances"]] == [first]
    assert [(e["what"], e["detail"]) for e in row["history"][-3:]] == [
        ("Instance added", first), ("Instance added", second), ("Instance removed", second)]
    assert conn.execute("SELECT COUNT(*) FROM code_instances").fetchone()[0] == 2


def test_text_added_before_links_only_still_shows(conn):
    conn.execute("INSERT INTO code_instances (code, kind, value, added_at) "
                 "VALUES ('RSVD22', 'text', 'Box 3', 't')")
    assert [(i["where"], i["url"]) for i in by_code(conn)["RSVD22"]["instances"]] == [("Text", None)]


@pytest.mark.parametrize("code,value,status,msg", [
    ("RSVD22", "  ", 400, "not a link"), ("RSVD22", "Box 3", 400, "not a link"),
    ("RSVD22", "familysearch.org/ark:/61903", 400, "not a link"),
    ("NOPE22", "https://example.org", 404, "not in the ledger"),
    ("JYMZ", "https://example.org", 409, "withdrawn"),
    ("RSVD22", "https://example.org/" + "x" * 2000, 400, "too long")])
def test_instance_refusals(conn, code, value, status, msg):
    with pytest.raises(codes.CodeError, match=msg) as exc:
        codes.add_instance(conn, code, value)
    assert exc.value.status == status


def test_instance_duplicates_and_removals(conn):
    url = "https://example.org/box-3"
    codes.add_instance(conn, "RSVD22", url)
    with pytest.raises(codes.CodeError, match="already lists") as exc:
        codes.add_instance(conn, "RSVD22", f" {url} ")
    assert exc.value.status == 409
    first = by_code(conn)["RSVD22"]["instances"][0]["id"]
    with pytest.raises(codes.CodeError) as exc:
        codes.remove_instance(conn, "PENCHD", first)
    assert exc.value.status == 404
    codes.remove_instance(conn, "RSVD22", first)
    with pytest.raises(codes.CodeError) as exc:
        codes.remove_instance(conn, "RSVD22", first)
    assert exc.value.status == 404
    codes.add_instance(conn, "RSVD22", url)
    assert [i["text"] for i in by_code(conn)["RSVD22"]["instances"]] == [url]


def test_migration_16_keeps_earlier_description_changes(tmp_path):
    path = tmp_path / "v15.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    for number, script in enumerate(db.MIGRATIONS[:15], start=1):
        old.executescript(script)
        old.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
    old.executemany("INSERT INTO reserved_ids (gramps_id, created_at, note) VALUES (?, ?, ?)",
                    [("EDIT22", "2026-09-01T10:00:00", "First words"),
                     ("SAME22", "2026-09-01T10:00:00", "Unchanged")])
    old.executemany("INSERT INTO objects (object_id, kind, note, updated_at) VALUES (?, ?, ?, ?)",
                    [("EDIT22", "item", "Second words", "2026-09-02T10:00:00"),
                     ("SAME22", "item", "Unchanged", "2026-09-01T10:00:00"),
                     ("GRUP22", "group", None, "2026-09-03T10:00:00")])
    old.commit()
    old.close()
    conn = db.connect(path)
    assert [tuple(r) for r in conn.execute("SELECT code, changed_at, note FROM code_descriptions")] == [
        ("EDIT22", "2026-09-02T10:00:00", "Second words")]
    conn.close()


# ---- export

def test_csv_columns_and_utf8_bom(conn):
    codes.update(conn, "RSVD22", {"note": "Brev från Värmland, Norra Ny"})
    codes.add_instance(conn, "RSVD22", "https://example.org/box-3")
    codes.add_instance(conn, "RSVD22", "https://example.org/brev")
    text = codes.to_csv(codes.rows(conn, {MNTD22}, URLS))
    assert text.startswith("\ufeff")
    table = list(csv.reader(io.StringIO(text[1:])))
    assert tuple(table[0]) == codes.CSV_COLUMNS
    rows = {r[0]: dict(zip(table[0], r)) for r in table[1:]}
    assert rows["RSVD22"]["note"] == "Brev från Värmland, Norra Ny"
    assert rows["RSVD22"]["instances"] == "https://example.org/box-3 | https://example.org/brev"
    assert (rows[MNTD22]["type"], rows[GONE]["type"], rows["RSVD22"]["type"]) == (
        "image", "document", "")
    assert rows[GONE]["needs_attention"] and rows[GONE]["in_gramps"] == "no"
    assert rows[GONE]["paperless_docs"] == "101 99"
    assert rows[GONE]["paperless_urls"].split()[0] == "https://docs.example/documents/101/details"
    assert rows[MNTD22]["immich_urls"] == "https://img.example/photos/asset-1"
    assert rows["JYMZ"]["status"] == "withdrawn" and "media-ui" in rows["JYMZ"]["withdrawn_reason"]
    assert "Värmland".encode() in text.encode("utf-8")


# ---- HTTP routes

class CodesGramps:
    def __init__(self, live=(MNTD22,), down=False, titles=None):
        self.live, self.down, self.calls = set(live), down, 0
        self.titles = titles or {}

    async def list_media_gramps_ids(self):
        self.calls += 1
        if self.down:
            raise GrampsError("GET /media/ → 502: bad gateway")
        return set(self.live)

    async def media_descriptions(self):
        return {g: self.titles.get(g, "") for g in await self.list_media_gramps_ids()}

    async def get_media_by_gramps_id(self, gramps_id):
        return {"handle": f"h-{gramps_id}"} if gramps_id in self.live else None

    async def media_thumbnail(self, handle, size=64):
        return f"thumb:{handle}:{size}".encode(), "image/avif"


class CodesPaperless:
    def __init__(self, values=None, down=False, docs=(7, 99, 101)):
        self.values, self.down = values or {7: "PPR222", 8: "  "}, down
        self.docs = set(docs)

    async def custom_field_values(self, field_id):
        assert field_id == 12
        if self.down:
            raise PaperlessError("GET /api/documents/ → 503: unavailable")
        return dict(self.values)

    async def document_ids(self):
        if self.down:
            raise PaperlessError("GET /api/documents/ → 503: unavailable")
        return set(self.docs)


def make_app(conn, gramps=None, paperless=None):
    app = FastAPI()
    app.include_router(codes_routes.router)
    app.state.conn = conn
    app.state.gramps = gramps or CodesGramps()
    app.state.paperless = paperless or CodesPaperless()
    app.state.cfg = SimpleNamespace(
        sync_paperless=SyncPaperlessConfig(public_url="https://docs.example",
                                           gramps_public_url="https://gramps.example",
                                           gramps_id_field_id=12),
        sync_immich=SyncImmichConfig(public_url="https://img.example"))
    return app


def call(app, method, url, **kw):
    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://bifrost") as client:
            return await client.request(method, url, **kw)
    return asyncio.run(go())


def test_api_list_filters(conn):
    app = make_app(conn)
    body = call(app, "GET", "/codes/api/list").json()
    assert body["gramps"] == "ok" and body["counts"]["attention"] == 1
    assert len(body["items"]) == body["counts"]["all"] == 10
    got = call(app, "GET", "/codes/api/list", params={"status": "needs attention"}).json()
    assert [r["code"] for r in got["items"]] == [GONE]
    got = call(app, "GET", "/codes/api/list", params={"status": "in use", "q": "mario"}).json()
    assert [r["code"] for r in got["items"]] == [MNTD22] and got["counts"]["all"] == 1
    assert call(app, "GET", "/codes/api/list", params={"status": "lost"}).status_code == 400


def test_api_list_checks_paperless_documents(conn):
    body = call(make_app(conn, paperless=CodesPaperless(docs=(99,))), "GET", "/codes/api/list").json()
    row = {r["code"]: r for r in body["items"]}[GONE]
    assert [d["id"] for d in row["paperless"]] == ["99"]
    assert row["attention"] == "Deleted from Gramps and Paperless"
    body = call(make_app(conn, paperless=CodesPaperless(down=True)), "GET", "/codes/api/list").json()
    assert [d["id"] for d in {r["code"]: r for r in body["items"]}[GONE]["paperless"]] == ["101", "99"]


def test_api_list_answers_without_gramps(conn):
    body = call(make_app(conn, gramps=CodesGramps(down=True)), "GET", "/codes/api/list").json()
    assert body["gramps"] == "unknown" and "502" in body["gramps_error"]
    rows = {r["code"]: r for r in body["items"]}
    assert rows[GONE]["status"] == "in use" and rows[GONE]["gramps"] is None


def test_api_mint(conn, script_ids):
    script_ids("PPR222", "FRESH2", "FRESH3")
    r = call(make_app(conn), "POST", "/codes/api/mint",
             json={"kind": "item", "note": "Loose print", "location": "b3c1", "count": 2})
    assert r.status_code == 200, r.text
    assert r.json()["codes"] == ["FRESH2", "FRESH3"]
    assert [i["location"] for i in r.json()["items"]] == ["B3.C1", "B3.C1"]
    assert all(i["status"] == "reserved" for i in r.json()["items"])


@pytest.mark.parametrize("gramps,paperless,name", [
    (CodesGramps(down=True), None, "Gramps"), (None, CodesPaperless(down=True), "Paperless")])
def test_api_mint_needs_every_system_readable(conn, gramps, paperless, name):
    r = call(make_app(conn, gramps=gramps, paperless=paperless), "POST", "/codes/api/mint",
             json={"kind": "item", "note": "Loose print"})
    assert r.status_code == 503 and name in r.json()["detail"]
    assert conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0


def test_api_mint_checks_the_form_before_calling_out(conn):
    gramps = CodesGramps()
    r = call(make_app(conn, gramps=gramps), "POST", "/codes/api/mint",
             json={"note": "", "count": 0})
    assert r.status_code == 400 and "between 1 and 20" in r.json()["detail"]
    assert gramps.calls == 0


@pytest.mark.parametrize("code,status,msg", [
    ("frsh-22", 200, None), ("FRSH20", 400, "contains 0"), (MNTD22, 409, "already in use"),
    ("JYMZ", 409, "withdrawn"), ("B2C3F4", 400, "location mark"), ("PPR222", 409, "Paperless document 7"),
])
def test_api_claim(conn, code, status, msg):
    r = call(make_app(conn), "POST", "/codes/api/claim",
             json={"code": code, "kind": "item", "note": "Written in 2025"})
    assert r.status_code == status, r.text
    if msg:
        assert msg in r.json()["detail"]
    else:
        assert r.json()["codes"] == ["FRSH22"] and r.json()["items"][0]["status"] == "reserved"


def test_api_penciled_patch_withdraw(conn):
    app = make_app(conn)
    g = group(conn)
    r = call(app, "POST", "/codes/api/rsvd22/penciled")
    assert r.status_code == 200 and r.json()["item"]["status"] == "penciled"
    assert call(app, "POST", "/codes/api/RSVD22/penciled").status_code == 200
    r = call(app, "PATCH", "/codes/api/RSVD22", json={"parent": g, "location": "b3.c1"})
    assert r.status_code == 200, r.text
    assert (r.json()["item"]["parent"], r.json()["item"]["location"]) == (g, "B3.C1")
    assert call(app, "PATCH", "/codes/api/RSVD22", json={"parent": "RSVD22"}).status_code == 400
    assert call(app, "POST", "/codes/api/RSVD22/withdraw", json={"reason": ""}).status_code == 400
    r = call(app, "POST", "/codes/api/RSVD22/withdraw", json={"reason": "wrong print"})
    assert r.status_code == 200 and r.json()["item"]["status"] == "withdrawn"
    assert call(app, "POST", "/codes/api/NOPE22/penciled").status_code == 404


def test_api_list_and_patch_follow_the_digital_record(conn):
    app = make_app(conn, gramps=CodesGramps(titles={MNTD22: "Mario, First Communion 1952"}))
    rows = {r["code"]: r for r in call(app, "GET", "/codes/api/list").json()["items"]}
    assert rows[MNTD22]["title"] == "Mario, First Communion 1952"
    assert rows[MNTD22]["history"][0]["what"] == "Minted from Immich"
    r = call(app, "PATCH", f"/codes/api/{MNTD22}", json={"note": "My own words"})
    assert r.status_code == 409 and "Immich" in r.json()["detail"]
    r = call(app, "PATCH", "/codes/api/RSVD22", json={"note": "Loose print"})
    assert r.status_code == 200 and r.json()["item"]["history"][-1]["detail"] == "Loose print"


def test_api_pencil_twice_and_cross_out(conn):
    app = make_app(conn)
    call(app, "POST", "/codes/api/RSVD22/penciled")
    first, second = call(app, "POST", "/codes/api/RSVD22/penciled").json()["item"]["pencilings"]
    url = f"/codes/api/rsvd22/pencilings/{first['id']}/cross-out"
    r = call(app, "POST", url)
    assert r.status_code == 200, r.text
    assert r.json()["item"]["status"] == "penciled"
    assert [p["crossed"] is None for p in r.json()["item"]["pencilings"]] == [False, True]
    assert call(app, "POST", url).status_code == 409
    assert call(app, "POST", "/codes/api/RSVD22/pencilings/999/cross-out").status_code == 404


def test_api_instances_and_thumbnail(conn):
    app = make_app(conn)
    r = call(app, "POST", "/codes/api/rsvd22/instances", json={"value": "https://example.org/x"})
    assert r.status_code == 200, r.text
    [added] = r.json()["item"]["instances"]
    assert (added["where"], added["url"]) == ("Link", "https://example.org/x")
    assert call(app, "POST", "/codes/api/JYMZ/instances", json={"value": "x"}).status_code == 409
    r = call(app, "DELETE", f"/codes/api/RSVD22/instances/{added['id']}")
    assert r.status_code == 200 and r.json()["item"]["instances"] == []
    assert call(app, "DELETE", f"/codes/api/RSVD22/instances/{added['id']}").status_code == 404
    r = call(app, "GET", f"/codes/api/{MNTD22.lower()}/thumbnail")
    assert r.status_code == 200 and r.content == f"thumb:h-{MNTD22}:256".encode()
    assert r.headers["content-type"] == "image/avif"
    assert call(app, "GET", "/codes/api/RSVD22/thumbnail").status_code == 404


def test_api_export_csv(conn):
    r = call(make_app(conn), "GET", "/codes/api/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")
    header = next(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert tuple(header) == codes.CSV_COLUMNS


def test_page_route_redirects_to_the_section(conn):
    r = call(make_app(conn), "GET", "/codes")
    assert r.status_code == 307 and r.headers["location"] == "/#codes"


# ---- the Paperless read behind the mint

def test_custom_field_values_reads_every_page():
    seen = []

    def serve(request):
        seen.append(dict(request.url.params))
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json={"next": None, "results": [
                {"id": 3, "custom_fields": [{"field": 12, "value": "THREE3"}]}]})
        return httpx.Response(200, json={
            "next": "http://paperless/api/documents/?page=2",
            "results": [{"id": 1, "custom_fields": [{"field": 12, "value": "PHKN3D"}]},
                        {"id": 2, "custom_fields": [{"field": 12, "value": " "}]}]})

    client = PaperlessClient("http://paperless", "token")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    assert asyncio.run(client.custom_field_values(12)) == {1: "PHKN3D", 3: "THREE3"}
    assert seen[0]["custom_fields__id__all"] == "12" and seen[0]["fields"] == "id,custom_fields"


# ---- the manual id path of the Immich sync

def run_one(conn, gramps_id, gramps=None, immich=None):
    async def collect():
        return [e async for e in sync_immich.sync_one_asset(
            gramps or FakeGramps(), [immich or FakeImmich(assets={"a1": asset("a1")})], conn, CFG,
            "a1", gramps_id=gramps_id)]
    return asyncio.run(collect())


@pytest.mark.parametrize("gid,msg", [("b2c3f4", "location mark"), ("234567", "all digits"),
                                     ("README", "reserved word")])
def test_manual_id_refuses_guarded_shapes(conn, gid, msg):
    with pytest.raises(SyncError, match=msg) as exc:
        run_one(conn, gid)
    assert exc.value.status == 400


def test_manual_id_refuses_a_withdrawn_code(conn):
    codes.withdraw(conn, "RSVD22", "penciled on the wrong print")
    with pytest.raises(SyncError, match="issued before") as exc:
        run_one(conn, "RSVD22")
    assert exc.value.status == 400


def test_manual_id_mints_a_reservation_that_has_a_scan(conn):
    conn.execute("INSERT INTO scan_register (scan_no, object_id) VALUES ('a000278', 'RSVD22')")
    conn.commit()
    events = run_one(conn, "rsvd22")
    assert summary_of(events).data["gramps_id"] == "RSVD22"
    row = by_code(conn, live={"RSVD22", MNTD22})["RSVD22"]
    assert row["status"] == "in use" and row["immich"][0]["id"] == "a1"


def test_manual_id_brings_the_codes_notes_to_the_photo(conn):
    codes.update(conn, "RSVD22", {"notes": "Penciled on the back, lower left"})
    immich = FakeImmich(assets={"a1": asset("a1")})
    run_one(conn, "rsvd22", immich=immich)
    assert sync_immich.note_for(conn, "a1", "RSVD22")["text"] == "Penciled on the back, lower left"
    assert immich.metadata["a1"]["bifrost"]["notes"] == "Penciled on the back, lower left"
    assert by_code(conn, live={"RSVD22", MNTD22})["RSVD22"]["notes"] == ""


def test_brought_notes_join_the_photos_own_notes_once(conn):
    codes.update(conn, "RSVD22", {"notes": "From the Codes page"})
    conn.execute("INSERT INTO photo_notes (asset_id, text, updated_at) VALUES ('a1', 'From Photos', 't')")
    conn.commit()
    sync_immich.bring_code_notes(conn, "a1", "RSVD22")
    sync_immich.bring_code_notes(conn, "a1", "RSVD22")
    assert sync_immich.note_for(conn, "a1", "RSVD22")["text"] == "From Photos\n\nFrom the Codes page"


# ---- notes

def test_notes_are_kept_apart_from_the_description(conn):
    codes.update(conn, "RSVD22", {"notes": "  Found in the blue album.\nBack is torn.  "})
    row = by_code(conn)["RSVD22"]
    assert row["notes"] == "Found in the blue album.\nBack is torn."
    assert row["note"] == "Reserved, not written yet"
    assert [r["code"] for r in codes.search(list(by_code(conn).values()), "blue album")] == ["RSVD22"]
    codes.update(conn, "RSVD22", {"notes": ""})
    row = by_code(conn)["RSVD22"]
    assert row["notes"] == "" and codes.notes_of(conn, "rsvd22") == ""
    assert [(e["what"], e["detail"]) for e in row["history"][-2:]] == [
        ("Notes changed", "Found in the blue album.\nBack is torn."), ("Notes cleared", None)]


def test_codes_with_a_record_keep_no_notes(conn):
    conn.execute("INSERT INTO photo_notes (asset_id, gramps_id, text, updated_at) "
                 "VALUES ('asset-1', ?, 'Written in Photos', 't')", (MNTD22,))
    for code, where in [(MNTD22, "Immich"), (GONE, "Paperless document 101")]:
        assert by_code(conn)[code]["notes"] == ""
        with pytest.raises(codes.CodeError, match=f"is in {where}") as exc:
            codes.update(conn, code, {"notes": "Something else"})
        assert exc.value.status == 409
        codes.update(conn, code, {"notes": ""})
    assert conn.execute("SELECT COUNT(*) FROM code_notes").fetchone()[0] == 0


def test_open_codes_are_the_ones_a_photo_can_take(conn):
    codes.update(conn, "RSVD22", {"notes": "Blue album"})
    assert [(c["code"], c["status"], c["notes"]) for c in codes.open_codes(conn, {MNTD22})] == [
        ("PENCHD", "penciled", ""), ("RSVD22", "reserved", "Blue album")]
    codes.withdraw(conn, "PENCHD", "wrong print")
    assert codes.open_codes(conn, {MNTD22, "RSVD22"}) == []


def test_api_notes_and_open_codes(conn):
    app = make_app(conn)
    r = call(app, "PATCH", "/codes/api/RSVD22", json={"notes": "Blue album"})
    assert r.status_code == 200 and r.json()["item"]["notes"] == "Blue album"
    assert [c["code"] for c in call(app, "GET", "/codes/api/open").json()["items"]] == [
        "PENCHD", "RSVD22"]
    down = make_app(conn, gramps=CodesGramps(down=True))
    assert call(down, "GET", "/codes/api/open").status_code == 503


def test_migration_19_moves_the_description_log(tmp_path):
    path = tmp_path / "v18.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    for number, script in enumerate(db.MIGRATIONS[:18], start=1):
        old.executescript(script)
        old.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
    old.execute("INSERT INTO code_notes (code, changed_at, note) "
                "VALUES ('EDIT22', '2026-09-02T10:00:00', 'Second words')")
    old.commit()
    old.close()
    conn = db.connect(path)
    assert [tuple(r) for r in conn.execute("SELECT code, changed_at, note FROM code_descriptions")] == [
        ("EDIT22", "2026-09-02T10:00:00", "Second words")]
    assert conn.execute("SELECT COUNT(*) FROM code_notes").fetchone()[0] == 0
    conn.close()


# ---- successors and deleting unused reservations

def test_a_withdrawn_code_names_its_successor(conn):
    codes.withdraw(conn, "rsvd22", "penciled on the wrong print", successor="pen-chd")
    rows = by_code(conn)
    assert rows["RSVD22"]["successor"] == "PENCHD" and rows["PENCHD"]["predecessors"] == ["RSVD22"]
    codes.update(conn, "RSVD22", {"successor": MNTD22})
    rows = by_code(conn)
    assert rows["RSVD22"]["successor"] == MNTD22
    assert rows["PENCHD"]["predecessors"] == [] and rows[MNTD22]["predecessors"] == ["RSVD22"]
    codes.update(conn, "RSVD22", {"successor": ""})
    assert by_code(conn)["RSVD22"]["successor"] is None


@pytest.mark.parametrize("successor,msg", [
    ("RSVD22", "can't replace itself"), ("NOPE22", "not in the ledger"), ("JYMZ", "is withdrawn")])
def test_successor_refusals(conn, successor, msg):
    with pytest.raises(codes.CodeError, match=msg) as exc:
        codes.withdraw(conn, "RSVD22", "wrong print", successor=successor)
    assert exc.value.status == 400
    assert by_code(conn)["RSVD22"]["status"] == "reserved"


def test_only_withdrawn_codes_have_successors(conn):
    with pytest.raises(codes.CodeError, match="not withdrawn") as exc:
        codes.update(conn, "RSVD22", {"successor": "PENCHD"})
    assert exc.value.status == 409


def test_deleting_an_unused_reservation(conn, script_ids):
    codes.update(conn, "RSVD22", {"note": "Loose print", "notes": "Box 3"})
    codes.add_instance(conn, "RSVD22", "https://example.org/x")
    assert by_code(conn)["RSVD22"]["deletable"] is True
    assert codes.delete(conn, "rsvd22", live={MNTD22}, paperless={}) == "RSVD22"
    assert "RSVD22" not in by_code(conn)
    for table, column in (("reserved_ids", "gramps_id"), ("objects", "object_id"),
                          ("code_descriptions", "code"), ("code_notes", "code"),
                          ("code_instances", "code")):
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column}='RSVD22'").fetchone()[0] == 0
    script_ids("RSVD22")
    assert codes.mint(conn, kind="item", note=None) == ["RSVD22"]


def test_used_codes_are_not_deletable(conn):
    codes.mark_penciled(conn, "RSVD22")
    first = by_code(conn)["RSVD22"]["pencilings"][0]["id"]
    codes.cross_out_penciling(conn, "RSVD22", first)
    rows = by_code(conn, live={MNTD22, "GRMP22"})
    assert [c for c, r in rows.items() if r["deletable"]] == []
    for code in ("RSVD22", "PENCHD", MNTD22, GONE, "JYMZ", "SCAN22"):
        with pytest.raises(codes.CodeError) as exc:
            codes.delete(conn, code, live={MNTD22}, paperless={})
        assert exc.value.status == 409
    with pytest.raises(codes.CodeError) as exc:
        codes.delete(conn, "NOPE22")
    assert exc.value.status == 404


def test_deleting_refuses_codes_held_elsewhere(conn):
    conn.execute("INSERT INTO reserved_ids (gramps_id, created_at) VALUES ('FREE22', 't')")
    for live, paperless in (({"FREE22"}, {}), (set(), {"FREE22": [7]})):
        with pytest.raises(codes.CodeError, match="can only be withdrawn"):
            codes.delete(conn, "FREE22", live=live, paperless=paperless)
    codes.withdraw(conn, "PENCHD", "wrong print", successor="FREE22")
    with pytest.raises(codes.CodeError, match="replaces PENCHD"):
        codes.delete(conn, "FREE22", live=set(), paperless={})


def test_api_delete_and_successor(conn):
    app = make_app(conn)
    r = call(app, "POST", "/codes/api/PENCHD/withdraw", json={"reason": "wrong print", "successor": "mntd22"})
    assert r.status_code == 200 and r.json()["item"]["successor"] == MNTD22
    r = call(app, "PATCH", "/codes/api/PENCHD", json={"successor": ""})
    assert r.status_code == 200 and r.json()["item"]["successor"] is None
    assert call(app, "DELETE", "/codes/api/RSVD22").json() == {"deleted": "RSVD22"}
    assert call(app, "DELETE", f"/codes/api/{MNTD22}").status_code == 409
    down = make_app(conn, gramps=CodesGramps(down=True))
    assert call(down, "DELETE", "/codes/api/SCAN22").status_code == 503


def test_csv_leaves_out_groups_locations_scans_and_notes(conn):
    header = next(csv.reader(io.StringIO(codes.to_csv(codes.rows(conn, {MNTD22}, URLS))[1:])))
    assert not {"kind", "part_of", "location", "items_in_group", "notes", "scans"} & set(header)
    assert {"note", "title", "instances", "created"} <= set(header)
