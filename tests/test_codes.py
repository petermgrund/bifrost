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
from bifrost.modules import codes, reconcile
from bifrost.web.routes import codes as codes_routes

# GONE: minted, then its media was deleted from Gramps; MNTD22: minted and live
GONE, MNTD22 = "XJ4DBT", "MNTD22"
SEEDED = {GONE, MNTD22, "RSVD22", "PENCHD"}
RETIRED = {"C8T5", "J82D", "JYMZ", "6H2P", "G8NQ"}
URLS = codes.Urls(gramps="https://gramps.example", paperless="https://docs.example",
                  immich="https://img.example")


def seed(conn):
    conn.executemany(
        "INSERT INTO minted_media (gramps_id, source_system, source_id, created_at, minted_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [(GONE, "paperless", "101", "2026-01-01T10:00:00", "2026-01-01T10:00:00"),
         (MNTD22, "immich", "asset-1", "2026-02-01T10:00:00", "2026-02-01T10:00:00")])
    conn.executemany(
        "INSERT INTO minted_media (gramps_id, created_at) VALUES (?, ?)",
        [("RSVD22", "2026-03-01T10:00:00"), ("PENCHD", "2026-03-02T10:00:00")])
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


def by_code(conn, live=frozenset({MNTD22}), **kw):
    return {r["code"]: r for r in codes.rows(conn, None if live is None else set(live), URLS, **kw)}


def ledger_row(conn, code):
    return conn.execute("SELECT * FROM minted_media WHERE gramps_id=?", (code,)).fetchone()


def ledger_codes(conn):
    """The codes in the ledger besides the retired ones every fresh database holds"""
    return {r[0] for r in conn.execute("SELECT gramps_id FROM minted_media")} - RETIRED


# ---- migration 32: one ledger table

def test_migration_32_folds_the_ledger_into_minted_media(tmp_path):
    path = tmp_path / "v31.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    for number, script in enumerate(db.MIGRATIONS[:31], start=1):
        old.executescript(script)
        old.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
    old.executemany(
        "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) VALUES (?, ?, ?, ?, ?)",
        [(MNTD22, "immich", "asset-1", "Mario", "2026-02-01T10:00:00"),
         ("RSVMNT", "paperless", "7", "Letter", "2026-02-05T10:00:00")])
    old.executemany(
        "INSERT INTO reserved_ids (gramps_id, created_at, minted_at, note) VALUES (?, ?, ?, ?)",
        [("RSVMNT", "2026-01-20T10:00:00", "2026-02-05T10:00:00", "Letter"),
         ("RSVD22", "2026-03-01T10:00:00", None, "Loose print"),
         ("WDRSVD", "2026-03-03T10:00:00", None, None)])
    old.executemany(
        "INSERT INTO withdrawn_codes (code, withdrawn_at, reason, successor) VALUES (?, ?, ?, ?)",
        [("WDRSVD", "2026-04-01T10:00:00", "wrong print", "RSVD22"),
         ("WDONLY", "2026-04-02T10:00:00", "never reserved", None)])
    old.execute("INSERT INTO scan_register (scan_no, object_id) VALUES ('a000277', 'SCAN22')")
    old.execute("INSERT INTO objects (object_id, kind, note) VALUES ('RSVD22', 'item', 'Loose print')")
    old.commit()
    old.close()

    conn = db.connect(path)
    conn.row_factory = sqlite3.Row
    rows = {r["gramps_id"]: dict(r) for r in conn.execute("SELECT * FROM minted_media")}
    assert set(rows) == {MNTD22, "RSVMNT", "RSVD22", "WDRSVD", "WDONLY", "SCAN22"} | RETIRED
    assert set(rows[MNTD22]) == {"gramps_id", "source_system", "source_id", "created_at", "minted_at",
                                 "withdrawn_at", "withdrawn_reason", "superseded_by"}
    minted = rows[MNTD22]
    assert (minted["source_system"], minted["source_id"]) == ("immich", "asset-1")
    assert minted["created_at"] == minted["minted_at"] == "2026-02-01T10:00:00"
    assert minted["withdrawn_at"] is None
    reserved_then_minted = rows["RSVMNT"]
    assert (reserved_then_minted["source_system"], reserved_then_minted["source_id"]) == ("paperless", "7")
    assert (reserved_then_minted["created_at"], reserved_then_minted["minted_at"]) == (
        "2026-01-20T10:00:00", "2026-02-05T10:00:00")
    reserved = rows["RSVD22"]
    assert (reserved["source_system"], reserved["created_at"], reserved["withdrawn_at"]) == (
        None, "2026-03-01T10:00:00", None)
    withdrawn = rows["WDRSVD"]
    assert (withdrawn["created_at"], withdrawn["withdrawn_at"], withdrawn["withdrawn_reason"],
            withdrawn["superseded_by"]) == ("2026-03-03T10:00:00", "2026-04-01T10:00:00", "wrong print", "RSVD22")
    only_withdrawn = rows["WDONLY"]
    assert only_withdrawn["created_at"] == only_withdrawn["withdrawn_at"] == "2026-04-02T10:00:00"
    assert only_withdrawn["withdrawn_reason"] == "never reserved"
    scanned = rows["SCAN22"]
    assert scanned["created_at"] and scanned["source_system"] is None and scanned["withdrawn_at"] is None
    for code in RETIRED:
        assert rows[code]["withdrawn_at"] and "4-character" in rows[code]["withdrawn_reason"]
        assert rows[code]["created_at"] == rows[code]["withdrawn_at"]
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables.isdisjoint({"reserved_ids", "objects", "withdrawn_codes", "code_descriptions", "code_notes",
                              "code_instances", "scan_register", "face_pads", "immich_versions",
                              "immich_version_members", "dated_photos", "version_labels", "codes_new"})
    assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == len(db.MIGRATIONS)
    conn.close()


def test_a_fresh_ledger_holds_the_retired_codes_as_withdrawn(conn):
    rows = by_code(conn)
    assert {c for c, r in rows.items() if r["status"] == "withdrawn"} == RETIRED
    assert all("4-character" in rows[c]["withdrawn_reason"] for c in RETIRED)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO minted_media (gramps_id, source_system, created_at) VALUES ('HALF22', 'immich', 't')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO minted_media (gramps_id, source_system, source_id, created_at) "
                     "VALUES ('FLKR22', 'flickr', 'x', 't')")


# ---- the guards

@pytest.mark.parametrize("code,why", [
    ("222222", "all digits"), ("234567", "all digits"),
    ("B2C3F4", "location mark B2.C3.F4"), ("B23456", "location mark B23456"),
    ("S2C3F4", "location mark S2.C3.F4"), ("B2C345", "location mark B2.C345"),
    ("S1", "location mark S1"), ("B99F22", "location mark B99.F22"),
    ("README", "reserved word"), ("SCHEME", "reserved word"),
])
def test_guarded_shapes(code, why):
    assert why in ids.guard_reason(code)


@pytest.mark.parametrize("code", ["B36Z55", "B2YQHE", "B446TP", "B5KU2X", "B74XFT", "B788RV",
                                  "B9U4GF", "S4WVRG", "S7HP82", "BC2345", "PHKN3D", "XFETYZ"])
def test_real_ids_pass_the_guards(code):
    assert ids.guard_reason(code) is None


def test_generator_skips_guarded_candidates(script_ids):
    script_ids("222222", "B2C3F4", "README", "SCHEME", "FRESH2")
    assert ids.generate_gramps_id(set()) == "FRESH2"


# ---- minting and claiming

def test_mint_never_returns_a_used_withdrawn_or_guarded_code(conn, script_ids):
    codes.withdraw(conn, "PENCHD", "wrong print")
    script_ids(GONE, MNTD22, "RSVD22", "PENCHD", "GRMP22", "PPR222",
               "222222", "B2C3F4", "README", "FRESH2", "FRESH3")
    assert codes.mint(conn, 2, live={"GRMP22"}, paperless={"PPR222"}) == ["FRESH2", "FRESH3"]
    fresh = ledger_row(conn, "FRESH2")
    assert fresh["created_at"] and fresh["source_system"] is None and fresh["minted_at"] is None
    rows = by_code(conn)
    assert rows["FRESH2"]["status"] == "reserved" and rows["FRESH2"]["history"] == [
        {"at": fresh["created_at"], "what": "Created", "detail": None}]


@pytest.mark.parametrize("count", [0, 21, "2", None])
def test_mint_refusals_write_nothing(conn, count):
    with pytest.raises(codes.CodeError, match="between 1 and 20") as exc:
        codes.mint(conn, count)
    assert exc.value.status == 400 and ledger_codes(conn) == SEEDED


def test_claim_normalizes_and_registers(conn):
    assert codes.claim(conn, " frsh-22 ", live={"GRMP22"}, paperless={"PPR222": [7]}) == "FRSH22"
    row = by_code(conn)["FRSH22"]
    assert (row["status"], row["in_ledger"], row["deletable"]) == ("reserved", True, True)
    assert [e["what"] for e in row["history"]] == ["Created"]


@pytest.mark.parametrize("raw,status,msg", [
    ("", 400, "Type the code as it is written."),
    ("   ", 400, "Type the code as it is written."),
    ("FRSH20", 400, "FRSH20 contains 0, which no code uses."),
    ("FRSH2", 400, "FRSH2 has 5 characters; a code has exactly 6."),
    ("B2C3F4", 400, "looks like the location mark B2.C3.F4"),
    ("222222", 400, "is all digits"),
    (MNTD22, 409, "MNTD22 is already in use: minted from Immich asset asset-1 on 2026-02-01."),
    (GONE, 409, "XJ4DBT is already in use: minted from Paperless document 101 on 2026-01-01."),
    ("rsvd22", 409, "RSVD22 is already in the ledger: reserved since 2026-03-01."),
    ("JYMZ", 409, "A withdrawn code is never used again."),
    ("GRMP22", 409, "GRMP22 is already the ID of a Gramps media object."),
    ("PPR222", 409, "PPR222 is already in the Gramps ID field of Paperless document 7."),
])
def test_claim_refusals(conn, raw, status, msg):
    with pytest.raises(codes.CodeError, match=re.escape(msg)) as exc:
        codes.claim(conn, raw, live={"GRMP22"}, paperless={"PPR222": [7]})
    assert exc.value.status == status and ledger_codes(conn) == SEEDED


# ---- status and attention

def test_status_derivation(conn):
    rows = by_code(conn, live={MNTD22, "GRMP22", "RSVD22", "O0001"})
    assert rows["PENCHD"]["status"] == "reserved" and rows["PENCHD"]["gramps"] is False
    assert rows["RSVD22"]["status"] == "in use" and rows["RSVD22"]["type"] is None
    assert rows[MNTD22]["status"] == "in use" and rows[MNTD22]["attention"] is None
    assert (rows[MNTD22]["type"], rows[GONE]["type"]) == ("image", "document")
    assert rows[GONE]["status"] == "in use"
    assert rows["GRMP22"]["status"] == "in use" and rows["GRMP22"]["in_ledger"] is False
    assert "O0001" not in rows
    assert rows["JYMZ"]["status"] == "withdrawn"
    assert rows[MNTD22]["gramps_url"] == f"https://gramps.example/media/{MNTD22}"
    assert rows[MNTD22]["immich"] == [{"id": "asset-1", "url": "https://img.example/photos/asset-1"}]
    assert rows[GONE]["paperless"] == [
        {"id": "101", "url": "https://docs.example/documents/101/details"},
        {"id": "99", "url": "https://docs.example/documents/99/details"}]
    assert rows[GONE]["gramps_url"] is None


def test_the_three_attention_cases(conn):
    rows = by_code(conn, live={MNTD22, "GRMP22"})
    assert rows["GRMP22"]["attention"] == "In Gramps, but not in bifrost's ledger"
    assert rows[GONE]["attention"] == "Deleted from Gramps"
    assert by_code(conn, live={MNTD22}, documents={"99"})[GONE]["attention"] == "Deleted from Gramps and Paperless"
    assert by_code(conn, live={MNTD22, GONE}, documents={"99"})[GONE]["attention"] == "Deleted from Paperless"
    assert by_code(conn, live={MNTD22, GONE}, documents={"99", "101"})[GONE]["attention"] is None
    codes.withdraw(conn, MNTD22, "duplicate of another print")
    row = by_code(conn)[MNTD22]
    assert (row["status"], row["attention"]) == ("withdrawn", "Withdrawn, but still in Gramps")
    assert by_code(conn, live=set())[MNTD22]["attention"] is None
    assert codes.counts(codes.rows(conn, {MNTD22, "GRMP22"}, URLS))["attention"] == 3


def test_deleted_paperless_documents_drop_out(conn):
    assert [d["id"] for d in by_code(conn, documents={"99"})[GONE]["paperless"]] == ["99"]
    assert by_code(conn, live={MNTD22, GONE}, documents=set())[GONE]["paperless"] == []
    assert [d["id"] for d in by_code(conn, documents=None)[GONE]["paperless"]] == ["101", "99"]


def test_unknown_gramps_leaves_the_ledger_status(conn):
    rows = by_code(conn, live=None)
    assert (rows[GONE]["status"], rows[GONE]["attention"], rows[GONE]["gramps"]) == ("in use", None, None)
    assert rows["RSVD22"]["status"] == "reserved"
    assert rows[MNTD22]["gramps_url"] is None


def test_rows_sort_newest_first_and_counts(conn):
    items = codes.rows(conn, {MNTD22}, URLS)
    assert [r["code"] for r in items][-4:] == ["PENCHD", "RSVD22", MNTD22, GONE]
    assert [r["code"] for r in items][:5] == sorted(RETIRED)
    assert codes.counts(items) == {"all": len(SEEDED | RETIRED), "reserved": 2, "in use": 2,
                                   "withdrawn": len(RETIRED), "attention": 1}
    assert [r["code"] for r in codes.rows(conn, {MNTD22}, URLS, only=["xj4-dbt", "nope22"])] == [GONE]


def test_search(conn):
    codes.withdraw(conn, "RSVD22", "penciled on the wrong print", superseded_by="PENCHD")
    items = codes.rows(conn, {MNTD22}, URLS, titles={MNTD22: "Mario's First Communion"})

    def hits(q):
        return [r["code"] for r in codes.search(items, q)]

    assert hits("xj4-dbt") == [GONE]
    assert hits("communion") == [MNTD22]
    assert hits("wrong print") == ["RSVD22"]
    assert hits("penchd") == ["PENCHD", "RSVD22"]
    assert hits("99") == [GONE]
    assert hits("asset-1") == [MNTD22]
    assert hits("  ") == [r["code"] for r in items] and hits("nothing here") == []


@pytest.mark.parametrize("raw,wanted", [("", None), ("all", None), ("in_use", "in use"),
                                        ("In-Use", "in use"), ("needs attention", "attention"),
                                        ("attention", "attention"), ("withdrawn", "withdrawn")])
def test_status_filter(raw, wanted):
    assert codes.status_filter(raw) == wanted


def test_status_filter_rejects_garbage():
    with pytest.raises(ValueError):
        codes.status_filter("lost")


def test_matches(conn):
    rows = by_code(conn, live={MNTD22, "GRMP22"})
    assert all(codes.matches(r, None) for r in rows.values())
    assert sorted(c for c, r in rows.items() if codes.matches(r, "attention")) == ["GRMP22", GONE]
    assert sorted(c for c, r in rows.items() if codes.matches(r, "reserved")) == ["PENCHD", "RSVD22"]


# ---- history

def test_history_is_chronological(conn):
    assert by_code(conn)[MNTD22]["history"] == [
        {"at": "2026-02-01T10:00:00", "what": "Minted from Immich", "detail": None}]
    assert [e["what"] for e in by_code(conn)[GONE]["history"]] == ["Minted from Paperless document 101"]
    ids.register_minted(conn, "RSVD22", "immich", "asset-2", "2026-05-01T10:00:00")
    codes.withdraw(conn, "RSVD22", "wrong print")
    row = by_code(conn)["RSVD22"]
    assert [(e["what"], e["detail"]) for e in row["history"]] == [
        ("Created", None), ("Minted from Immich", None), ("Withdrawn", "wrong print")]
    assert [e["at"][:10] for e in row["history"]][:2] == ["2026-03-01", "2026-05-01"]
    assert row["updated"] == row["history"][-1]["at"] == row["withdrawn"]
    assert by_code(conn, live={"GRMP22"})["GRMP22"]["history"] == []


def test_title_comes_from_gramps(conn):
    rows = by_code(conn, titles={MNTD22: "Mario, First Communion 1952"})
    assert rows[MNTD22]["title"] == "Mario, First Communion 1952" and rows["RSVD22"]["title"] is None


# ---- withdraw, supersede, delete

def test_withdraw_blocks_reuse_and_deletes_nothing(conn, script_ids):
    assert codes.withdraw(conn, "rsvd22", "  penciled on the   wrong print ") == "RSVD22"
    gone = ledger_row(conn, "RSVD22")
    assert gone["withdrawn_reason"] == "penciled on the wrong print" and gone["withdrawn_at"]
    assert gone["created_at"] == "2026-03-01T10:00:00"
    assert by_code(conn)["RSVD22"]["status"] == "withdrawn"
    with pytest.raises(codes.CodeError, match="withdrawn on") as exc:
        codes.claim(conn, "RSVD22")
    assert exc.value.status == 409
    script_ids("RSVD22", "FRESH2")
    assert codes.mint(conn) == ["FRESH2"]
    assert "RSVD22" in ids.all_ids_ever_seen(conn, open_reservations=False)


@pytest.mark.parametrize("code,reason,status", [
    ("RSVD22", "", 400), ("RSVD22", "   ", 400), ("RSVD22", "x" * 1001, 400),
    ("", "a reason", 400), ("NOPE22", "a reason", 404), ("JYMZ", "again", 409),
])
def test_withdraw_refusals(conn, code, reason, status):
    with pytest.raises(codes.CodeError) as exc:
        codes.withdraw(conn, code, reason)
    assert exc.value.status == status
    assert by_code(conn).get("RSVD22", {}).get("status") == "reserved"


def test_a_withdrawn_code_names_the_code_that_supersedes_it(conn):
    codes.withdraw(conn, "rsvd22", "penciled on the wrong print", superseded_by="pen-chd")
    rows = by_code(conn)
    assert rows["RSVD22"]["superseded_by"] == "PENCHD" and rows["PENCHD"]["supersedes"] == ["RSVD22"]
    assert codes.supersede(conn, "RSVD22", MNTD22) == "RSVD22"
    rows = by_code(conn)
    assert rows["RSVD22"]["superseded_by"] == MNTD22
    assert rows["PENCHD"]["supersedes"] == [] and rows[MNTD22]["supersedes"] == ["RSVD22"]
    codes.supersede(conn, "RSVD22", "")
    assert by_code(conn)["RSVD22"]["superseded_by"] is None
    codes.supersede(conn, "RSVD22", None)
    assert by_code(conn)["RSVD22"]["superseded_by"] is None


@pytest.mark.parametrize("other,msg", [
    ("RSVD22", "can't supersede itself"), ("NOPE22", "not in the ledger"), ("JYMZ", "is withdrawn")])
def test_supersede_refusals(conn, other, msg):
    with pytest.raises(codes.CodeError, match=msg) as exc:
        codes.withdraw(conn, "RSVD22", "wrong print", superseded_by=other)
    assert exc.value.status == 400
    assert by_code(conn)["RSVD22"]["status"] == "reserved"
    codes.withdraw(conn, "RSVD22", "wrong print")
    with pytest.raises(codes.CodeError, match=msg) as exc:
        codes.supersede(conn, "RSVD22", other)
    assert exc.value.status == 400 and by_code(conn)["RSVD22"]["superseded_by"] is None


def test_only_withdrawn_codes_are_superseded(conn):
    with pytest.raises(codes.CodeError, match="not withdrawn") as exc:
        codes.supersede(conn, "RSVD22", "PENCHD")
    assert exc.value.status == 409
    with pytest.raises(codes.CodeError) as exc:
        codes.supersede(conn, "NOPE22", "PENCHD")
    assert exc.value.status == 404


def test_deleting_an_unused_reservation(conn, script_ids):
    assert by_code(conn)["RSVD22"]["deletable"] is True
    assert codes.delete(conn, "rsvd22", live={MNTD22}, paperless={}) == "RSVD22"
    assert "RSVD22" not in by_code(conn) and ledger_row(conn, "RSVD22") is None
    script_ids("RSVD22")
    assert codes.mint(conn) == ["RSVD22"]


def test_used_codes_are_not_deletable(conn):
    rows = by_code(conn, live={MNTD22, "GRMP22"})
    assert sorted(c for c, r in rows.items() if r["deletable"]) == ["PENCHD", "RSVD22"]
    for code in (MNTD22, GONE, "JYMZ"):
        with pytest.raises(codes.CodeError, match="can only be withdrawn") as exc:
            codes.delete(conn, code, live={MNTD22}, paperless={})
        assert exc.value.status == 409
    with pytest.raises(codes.CodeError) as exc:
        codes.delete(conn, "NOPE22")
    assert exc.value.status == 404
    assert ledger_codes(conn) == SEEDED


def test_deleting_refuses_codes_held_elsewhere(conn):
    for live, paperless in (({"RSVD22"}, {}), (set(), {"RSVD22": [7]})):
        with pytest.raises(codes.CodeError, match="can only be withdrawn"):
            codes.delete(conn, "RSVD22", live=live, paperless=paperless)
    assert by_code(conn, live={"RSVD22"})["RSVD22"]["deletable"] is False
    codes.withdraw(conn, "PENCHD", "wrong print", superseded_by="RSVD22")
    with pytest.raises(codes.CodeError, match="RSVD22 supersedes PENCHD"):
        codes.delete(conn, "RSVD22", live=set(), paperless={})


# ---- open codes and the CSV

def test_open_codes_are_the_ones_a_photo_can_take(conn):
    assert codes.open_codes(conn, {MNTD22}) == [
        {"code": "PENCHD", "status": "reserved", "created": "2026-03-02T10:00:00"},
        {"code": "RSVD22", "status": "reserved", "created": "2026-03-01T10:00:00"}]
    assert [c["code"] for c in codes.open_codes(conn, {MNTD22, "RSVD22", "GRMP22"})] == ["PENCHD"]
    codes.withdraw(conn, "PENCHD", "wrong print")
    assert codes.open_codes(conn, {MNTD22, "RSVD22"}) == []


def test_csv_columns_and_utf8_bom(conn):
    codes.withdraw(conn, "RSVD22", "wrong print", superseded_by="PENCHD")
    text = codes.to_csv(codes.rows(conn, {MNTD22}, URLS, titles={MNTD22: "Värmland"}))
    assert text.startswith("﻿")
    reader = csv.DictReader(io.StringIO(text[1:]))
    assert tuple(reader.fieldnames) == codes.CSV_COLUMNS
    rows = {r["code"]: r for r in reader}
    assert set(rows) == SEEDED | RETIRED
    assert rows[MNTD22]["title"] == "Värmland" and rows[MNTD22]["in_gramps"] == "yes"
    assert rows[MNTD22]["immich_assets"] == "asset-1"
    assert rows[MNTD22]["immich_urls"] == "https://img.example/photos/asset-1"
    assert rows[GONE]["paperless_docs"] == "101 99" and rows[GONE]["needs_attention"] == "Deleted from Gramps"
    assert rows["RSVD22"]["withdrawn_reason"] == "wrong print" and rows["RSVD22"]["superseded_by"] == "PENCHD"
    assert rows["JYMZ"]["status"] == "withdrawn" and "4-character" in rows["JYMZ"]["withdrawn_reason"]
    assert rows["PENCHD"]["in_gramps"] == "no" and rows["PENCHD"]["minted"] == ""
    unknown = codes.to_csv(codes.rows(conn, None, URLS))
    assert {r["code"]: r for r in csv.DictReader(io.StringIO(unknown[1:]))}[MNTD22]["in_gramps"] == "unknown"


# ---- HTTP routes

class CodesGramps:
    def __init__(self, live=(MNTD22,), down=False, titles=None, media=None):
        self.live, self.down, self.calls = set(live), down, 0
        self.titles = titles or {}
        self.media = media

    async def list_media_gramps_ids(self):
        self.calls += 1
        if self.down:
            raise GrampsError("GET /media/ → 502: bad gateway")
        return set(self.live)

    async def media_descriptions(self):
        return {g: self.titles.get(g, "") for g in await self.list_media_gramps_ids()}

    async def list_media(self, keys=None):
        assert "attribute_list" in (keys or "")
        if self.down:
            raise GrampsError("GET /media/ → 502: bad gateway")
        return list(self.media or [])

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


class CodesImmich:
    def __init__(self, assets=None):
        self.assets = assets if assets is not None else {"asset-1": {"id": "asset-1"}, "asset-9": {"id": "asset-9"}}
        self.asked = []

    async def get_assets_many(self, asset_ids, concurrency=8):
        self.asked.append(list(asset_ids))
        return {a: self.assets.get(a) for a in asset_ids}


def make_app(conn, gramps=None, paperless=None, immich=None):
    app = FastAPI()
    app.include_router(codes_routes.router)
    app.state.conn = conn
    app.state.gramps = gramps or CodesGramps()
    app.state.paperless = paperless or CodesPaperless()
    app.state.immich_accounts = [immich] if immich else []
    app.state.caches = {"faces_gramps_people": []}
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
    app = make_app(conn, gramps=CodesGramps(titles={MNTD22: "Mario's First Communion"}))
    body = call(app, "GET", "/codes/api/list").json()
    assert body["gramps"] == "ok" and body["counts"]["attention"] == 1
    assert {r["code"] for r in body["items"]} == SEEDED | RETIRED and body["counts"]["all"] == len(body["items"])
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
    r = call(make_app(conn), "POST", "/codes/api/mint", json={"count": 2})
    assert r.status_code == 200, r.text
    assert r.json()["codes"] == ["FRESH2", "FRESH3"]
    assert [(i["code"], i["status"]) for i in r.json()["items"]] == [("FRESH2", "reserved"), ("FRESH3", "reserved")]
    script_ids("FRESH4")
    assert call(make_app(conn), "POST", "/codes/api/mint", json={}).json()["codes"] == ["FRESH4"]


@pytest.mark.parametrize("gramps,paperless,name", [
    (CodesGramps(down=True), None, "Gramps"), (None, CodesPaperless(down=True), "Paperless")])
def test_api_mint_needs_every_system_readable(conn, gramps, paperless, name):
    r = call(make_app(conn, gramps=gramps, paperless=paperless), "POST", "/codes/api/mint", json={})
    assert r.status_code == 503 and name in r.json()["detail"]
    assert ledger_codes(conn) == SEEDED


def test_api_mint_checks_the_form_before_calling_out(conn):
    gramps = CodesGramps()
    r = call(make_app(conn, gramps=gramps), "POST", "/codes/api/mint", json={"count": 0})
    assert r.status_code == 400 and "between 1 and 20" in r.json()["detail"]
    assert call(make_app(conn, gramps=gramps), "POST", "/codes/api/mint", json={"count": 21}).status_code == 400
    assert call(make_app(conn, gramps=gramps), "POST", "/codes/api/mint", json={"count": "two"}).status_code == 422
    assert gramps.calls == 0


@pytest.mark.parametrize("code,status,msg", [
    ("frsh-22", 200, None), ("", 400, "Type the code"), ("FRSH20", 400, "contains 0"),
    (MNTD22, 409, "already in use"), ("JYMZ", 409, "withdrawn"), ("B2C3F4", 400, "location mark"),
    ("PPR222", 409, "Paperless document 7"),
])
def test_api_claim(conn, code, status, msg):
    gramps = CodesGramps()
    r = call(make_app(conn, gramps=gramps), "POST", "/codes/api/claim", json={"code": code})
    assert r.status_code == status, r.text
    if msg:
        assert msg in r.json()["detail"]
        assert gramps.calls == (1 if code == "PPR222" else 0)
    else:
        assert r.json()["codes"] == ["FRSH22"] and r.json()["items"][0]["status"] == "reserved"


def test_api_withdraw_patch_and_delete(conn):
    app = make_app(conn)
    assert call(app, "POST", "/codes/api/RSVD22/withdraw", json={"reason": ""}).status_code == 400
    assert call(app, "PATCH", "/codes/api/RSVD22", json={"superseded_by": "PENCHD"}).status_code == 409
    r = call(app, "POST", "/codes/api/rsvd22/withdraw", json={"reason": "wrong print", "superseded_by": "pen-chd"})
    assert r.status_code == 200, r.text
    assert (r.json()["item"]["status"], r.json()["item"]["superseded_by"]) == ("withdrawn", "PENCHD")
    assert call(app, "POST", "/codes/api/RSVD22/withdraw", json={"reason": "again"}).status_code == 409
    assert call(app, "DELETE", "/codes/api/PENCHD").status_code == 409
    r = call(app, "PATCH", "/codes/api/RSVD22", json={"superseded_by": MNTD22})
    assert r.status_code == 200 and r.json()["item"]["superseded_by"] == MNTD22
    r = call(app, "PATCH", "/codes/api/RSVD22", json={})
    assert r.status_code == 200 and r.json()["item"]["superseded_by"] is None
    assert call(app, "PATCH", "/codes/api/RSVD22", json={"superseded_by": "RSVD22"}).status_code == 400
    assert call(app, "PATCH", "/codes/api/NOPE22", json={"superseded_by": ""}).status_code == 404
    assert call(app, "DELETE", "/codes/api/PENCHD").json() == {"deleted": "PENCHD"}
    assert call(app, "DELETE", f"/codes/api/{MNTD22}").status_code == 409
    assert call(app, "DELETE", "/codes/api/NOPE22").status_code == 404
    assert call(make_app(conn, gramps=CodesGramps(down=True)), "DELETE", "/codes/api/RSVD22").status_code == 503
    assert ledger_codes(conn) == SEEDED - {"PENCHD"}


def test_api_thumbnail(conn):
    app = make_app(conn)
    r = call(app, "GET", f"/codes/api/{MNTD22.lower()}/thumbnail")
    assert r.status_code == 200 and r.content == f"thumb:h-{MNTD22}:256".encode()
    assert r.headers["content-type"] == "image/avif"
    assert call(app, "GET", f"/codes/api/{MNTD22}/thumbnail", params={"size": 64}).content.endswith(b":64")
    assert call(app, "GET", "/codes/api/RSVD22/thumbnail").status_code == 404


def test_api_open_codes(conn):
    assert [c["code"] for c in call(make_app(conn), "GET", "/codes/api/open").json()["items"]] == [
        "PENCHD", "RSVD22"]
    assert call(make_app(conn, gramps=CodesGramps(down=True)), "GET", "/codes/api/open").status_code == 503


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


# ---- reconcile

def attr(name, value):
    return {"type": name, "value": value}


def reconcile_app(conn, immich=None, media=None):
    codes.withdraw(conn, "PENCHD", "wrong print")
    media = media if media is not None else [
        {"gramps_id": MNTD22, "desc": "Mario", "attribute_list": [attr("Immich ID", "asset-1")]},
        {"gramps_id": "GRMP22", "desc": "Loose print", "attribute_list": [attr("Immich ID", "asset-9")]},
        {"gramps_id": "HAND22", "desc": "Written by hand", "attribute_list": []},
        {"gramps_id": "PENCHD", "desc": "Old scan", "attribute_list": []},
        {"gramps_id": "O0001", "desc": "Default id", "attribute_list": []},
    ]
    gramps = CodesGramps(live=[m["gramps_id"] for m in media], media=media)
    return make_app(conn, gramps=gramps, immich=immich or CodesImmich())


def items_of(body):
    return {e["source_id"]: e for e in body["events"] if e["kind"] == "item"}


def summary_of(body):
    return next(e["data"] for e in body["events"] if e["kind"] == "summary")


def test_api_reconcile_config(conn):
    assert call(make_app(conn), "GET", "/codes/api/reconcile/config").json() == {"enabled": True}


def test_api_reconcile_preview_changes_nothing(conn):
    app = reconcile_app(conn)
    r = call(app, "POST", "/codes/api/reconcile/preview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["apply"] is False and body["run_id"]
    items = items_of(body)
    assert {k: v["action"] for k, v in items.items()} == {
        "GRMP22": "would_create", "HAND22": "would_create", GONE: "would_update", "PENCHD": "failed"}
    assert all(e["entity"] == "media" and e["gramps_id"] == e["source_id"] for e in items.values())
    assert items["GRMP22"]["data"]["cols"] == {"source": "Immich asset asset-9"}
    assert items["HAND22"]["data"]["cols"] == {"source": "none"}
    assert items[GONE]["data"]["cols"] == {"gramps": "deleted → withdrawn"}
    assert "still in Gramps" in items["PENCHD"]["detail"]
    assert summary_of(body) == {"registered": 0, "repointed": 0, "withdrawn": 0, "attention": 1, "errors": 0}
    assert ledger_row(conn, "GRMP22") is None and ledger_row(conn, GONE)["withdrawn_at"] is None
    assert app.state.immich_accounts[0].asked == [["asset-1"]]
    assert conn.execute("SELECT job FROM runs WHERE id=?", (body["run_id"],)).fetchone()[0] == "codes.reconcile.preview"


def test_api_reconcile_apply_selected(conn):
    app = reconcile_app(conn)
    r = call(app, "POST", "/codes/api/reconcile/apply", json={"selected": ["media:GRMP22"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["apply"] is True
    items = items_of(body)
    assert (items["GRMP22"]["action"], items["HAND22"]["action"], items[GONE]["action"]) == (
        "created", "would_create", "would_update")
    assert summary_of(body)["registered"] == 1 and summary_of(body)["withdrawn"] == 0
    row = ledger_row(conn, "GRMP22")
    assert (row["source_system"], row["source_id"]) == ("immich", "asset-9") and row["minted_at"]
    assert ledger_row(conn, "HAND22") is None and ledger_row(conn, GONE)["withdrawn_at"] is None
    assert app.state.caches == {}
    assert conn.execute("SELECT job FROM runs WHERE id=?", (body["run_id"],)).fetchone()[0] == "codes.reconcile"


def test_api_reconcile_apply_everything(conn):
    app = reconcile_app(conn)
    body = call(app, "POST", "/codes/api/reconcile/apply", json={}).json()
    assert summary_of(body) == {"registered": 2, "repointed": 0, "withdrawn": 1, "attention": 1, "errors": 0}
    hand = ledger_row(conn, "HAND22")
    assert hand["source_system"] is None and hand["minted_at"] is None and hand["created_at"]
    gone = ledger_row(conn, GONE)
    assert gone["withdrawn_at"] and gone["withdrawn_reason"] == reconcile.DELETED_REASON
    rows = by_code(conn, live={MNTD22, "GRMP22", "HAND22", "PENCHD"})
    assert (rows["GRMP22"]["status"], rows["HAND22"]["status"], rows[GONE]["status"]) == (
        "in use", "in use", "withdrawn")
    assert call(app, "POST", "/codes/api/reconcile/preview").json()["events"][-1]["data"]["attention"] == 1


def test_api_reconcile_follows_a_moved_source_and_flags_trashed_assets(conn):
    media = [{"gramps_id": MNTD22, "desc": "Mario", "attribute_list": [attr("Immich ID", "asset-2")]},
             {"gramps_id": GONE, "desc": "Letter", "attribute_list": [attr("Paperless ID", "101")]}]
    immich = CodesImmich(assets={"asset-1": {"id": "asset-1"}, "asset-2": {"id": "asset-2", "isTrashed": True}})
    app = reconcile_app(conn, immich=immich, media=media)
    body = call(app, "POST", "/codes/api/reconcile/preview").json()
    rows = [(e["source_id"], e["action"], e.get("detail"), (e.get("data") or {}).get("cols"))
            for e in body["events"] if e["kind"] == "item"]
    assert rows == [
        (MNTD22, "would_update", None, {"source": "Immich asset asset-1 → Immich asset asset-2"}),
        (MNTD22, "failed", "Immich asset asset-2 is in the trash", None)]
    assert summary_of(body)["attention"] == 1 and immich.asked == [["asset-2"]]
    body = call(app, "POST", "/codes/api/reconcile/apply", json={}).json()
    assert items_of(body)[MNTD22]["action"] in ("updated", "failed") and summary_of(body)["repointed"] == 1
    assert ledger_row(conn, MNTD22)["source_id"] == "asset-2"
    body = call(app, "POST", "/codes/api/reconcile/preview").json()
    failed = [e for e in body["events"] if e["kind"] == "item" and e["action"] == "failed"]
    assert [(e["source_id"], e["title"], e["detail"]) for e in failed] == [
        (MNTD22, "Mario", "Immich asset asset-2 is in the trash")]
    assert summary_of(body)["attention"] == 1 and immich.asked[-1] == ["asset-2"]


def test_api_reconcile_reports_unreachable_services(conn):
    class DownImmich:
        async def get_assets_many(self, asset_ids, concurrency=8):
            raise RuntimeError("immich is down")

    app = reconcile_app(conn, immich=DownImmich())
    body = call(app, "POST", "/codes/api/reconcile/preview").json()
    errors = [e["detail"] for e in body["events"] if e["kind"] == "error"]
    assert errors == ["Immich: immich is down; its records were not checked"]
    assert summary_of(body)["errors"] == 1 and items_of(body)["GRMP22"]["action"] == "would_create"


def test_api_reconcile_without_gramps(conn):
    app = make_app(conn, gramps=CodesGramps(down=True))
    body = call(app, "POST", "/codes/api/reconcile/preview").json()
    assert [e["kind"] for e in body["events"]] == ["error", "summary"]
    assert "nothing checked" in body["events"][0]["detail"]


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
