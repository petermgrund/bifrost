import asyncio

import pytest

from bifrost.core import db
from bifrost.modules import reconcile
from bifrost.modules.sync_immich import _attr
from test_sync_immich import FakeGramps, FakeImmich, asset, mint


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


def media(gid, handle="h1", desc="T", immich=None, paperless=None):
    attrs = ([_attr("Immich ID", immich)] if immich is not None else []) + \
            ([_attr("Paperless ID", paperless)] if paperless is not None else [])
    return {"gramps_id": gid, "handle": handle, "desc": desc, "attribute_list": attrs}


class FakePaperless:
    def __init__(self, ids=(), down=False):
        self.ids = set(ids)
        self.down = down

    async def document_ids(self):
        if self.down:
            raise RuntimeError("paperless down")
        return set(self.ids)


class DownImmich(FakeImmich):
    async def get_assets_many(self, asset_ids, concurrency=8):
        raise RuntimeError("immich down")


class CountingImmich(FakeImmich):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.requested = []

    async def get_assets_many(self, asset_ids, concurrency=8):
        self.requested.append(list(asset_ids))
        return await super().get_assets_many(asset_ids, concurrency)


class DownGramps(FakeGramps):
    async def list_media(self, keys=None):
        raise RuntimeError("gramps down")


def scan(gr, conn, paperless=None, accounts=(), apply=False, selected=None):
    async def collect():
        return [e async for e in reconcile.scan(gr, paperless, list(accounts), conn,
                                                apply=apply, selected=selected)]
    return asyncio.run(collect())


def items(events):
    return [e for e in events if e.kind == "item"]


def row(conn, code):
    r = conn.execute("SELECT * FROM minted_media WHERE gramps_id=?", (code,)).fetchone()
    return dict(r) if r else None


def live_rows(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM minted_media WHERE source_system IS NOT NULL ORDER BY gramps_id")]


def reserve(conn, code):
    with conn:
        conn.execute("INSERT INTO minted_media (gramps_id, created_at) VALUES (?, '2026-01-01')", (code,))


def withdraw(conn, code, when="2026-02-01T00:00:00+00:00"):
    with conn:
        conn.execute("UPDATE minted_media SET withdrawn_at=?, withdrawn_reason='old' WHERE gramps_id=?",
                     (when, code))


class TestExpectedFrom:
    def test_source_attributes_win(self):
        assert reconcile.expected_from([
            media("ABC123", desc="Farm", immich="a1"),
            media("O0001", desc="Deed", paperless="7"),
        ]) == {"ABC123": ("immich", "a1", "Farm"), "O0001": ("paperless", "7", "Deed")}

    def test_codes_without_a_source_are_included_and_other_ids_skipped(self):
        assert reconcile.expected_from([
            media("DEF456", desc="Manual"),
            media("O0001"),
            media("def456"),
            media("DEF45"),
            media("ABC123"),
            media(""),
            {"handle": "h"},
        ]) == {"DEF456": (None, None, "Manual")}

    def test_blank_values_count_as_no_source(self):
        m = media(" DEF456 ", desc=None)
        m["attribute_list"] = [_attr("Immich ID", "  "), {"type": "Other", "value": "x"}]
        assert reconcile.expected_from([m]) == {"DEF456": (None, None, "")}


class TestPreview:
    def test_a_media_the_ledger_lacks_would_be_created(self, conn):
        gr = FakeGramps(media={"ABC123": media("ABC123", desc="Farm", immich="a1"),
                               "DEF456": media("DEF456", desc="Manual"),
                               "O0001": media("O0001", desc="Deed", paperless="7")})
        events = scan(gr, conn)
        rows = items(events)
        assert [(r.action, r.entity, r.source_id, r.gramps_id, r.title, r.data) for r in rows] == [
            ("would_create", "media", "ABC123", "ABC123", "Farm", {"cols": {"source": "Immich asset a1"}}),
            ("would_create", "media", "DEF456", "DEF456", "Manual", {"cols": {"source": "none"}}),
            ("would_create", "media", "O0001", "O0001", "Deed", {"cols": {"source": "Paperless document 7"}})]
        assert live_rows(conn) == [] and row(conn, "DEF456") is None
        assert events[-1].data == {"registered": 0, "repointed": 0, "withdrawn": 0, "attention": 0, "errors": 0}

    def test_a_moved_source_would_be_updated(self, conn):
        mint(conn, "ABC123", "a1")
        mint(conn, "DEF456", "a2")
        gr = FakeGramps(media={"ABC123": media("ABC123", immich="a2"),
                               "DEF456": media("DEF456", paperless="7")})
        rows = items(scan(gr, conn, accounts=[FakeImmich(assets={"a1": asset("a1"), "a2": asset("a2")})]))
        assert [(r.action, r.gramps_id, r.data["cols"]) for r in rows] == [
            ("would_update", "ABC123", {"source": "Immich asset a1 → Immich asset a2"}),
            ("would_update", "DEF456", {"source": "Immich asset a2 → Paperless document 7"})]
        assert [r["source_id"] for r in live_rows(conn)] == ["a1", "a2"]

    def test_a_reservation_taken_in_gramps_would_be_updated(self, conn):
        reserve(conn, "ABC123")
        rows = items(scan(FakeGramps(media={"ABC123": media("ABC123", immich="a1")}), conn))
        assert [(r.action, r.data["cols"]) for r in rows] == [("would_update", {"source": "none → Immich asset a1"})]

    def test_a_matching_ledger_is_quiet(self, conn):
        mint(conn, "ABC123", "a1")
        mint(conn, "DEF456", "7", system="paperless")
        reserve(conn, "GHJ789")
        gr = FakeGramps(media={"ABC123": media("ABC123", immich="a1"), "DEF456": media("DEF456", paperless="7"),
                               "GHJ789": media("GHJ789")})
        events = scan(gr, conn, paperless=FakePaperless({7}), accounts=[FakeImmich(assets={"a1": asset("a1")})])
        assert items(events) == []
        assert events[-1].data == {"registered": 0, "repointed": 0, "withdrawn": 0, "attention": 0, "errors": 0}

    def test_a_ledger_row_whose_media_is_gone_would_be_withdrawn(self, conn):
        mint(conn, "ABC123", "a1")
        mint(conn, "DEF456", "7", system="paperless")
        reserve(conn, "GHJ789")
        rows = items(scan(FakeGramps(), conn))
        assert [(r.action, r.gramps_id, r.title, r.data) for r in rows] == [
            ("would_update", "ABC123", "Immich asset a1", {"cols": {"gramps": "deleted → withdrawn"}}),
            ("would_update", "DEF456", "Paperless document 7", {"cols": {"gramps": "deleted → withdrawn"}})]
        assert all(r["withdrawn_at"] is None for r in live_rows(conn))

    def test_a_withdrawn_code_still_in_gramps_needs_attention(self, conn):
        mint(conn, "ABC123", "a1")
        withdraw(conn, "ABC123")
        events = scan(FakeGramps(media={"ABC123": media("ABC123", desc="Farm", immich="a1")}), conn)
        rows = items(events)
        assert [(r.action, r.gramps_id, r.title, r.detail) for r in rows] == [
            ("failed", "ABC123", "Farm", "withdrawn on 2026-02-01, but still in Gramps")]
        assert events[-1].data["attention"] == 1

    def test_a_gone_or_trashed_immich_asset_needs_attention(self, conn):
        mint(conn, "ABC123", "a1")
        mint(conn, "DEF456", "a2")
        mint(conn, "GHJ789", "a3")
        gr = FakeGramps(media={"ABC123": media("ABC123", desc="Gone", immich="a1"),
                               "DEF456": media("DEF456", desc="Trashed", immich="a2"),
                               "GHJ789": media("GHJ789", desc="Fine", immich="a3")})
        im = FakeImmich(assets={"a2": {**asset("a2"), "isTrashed": True}, "a3": asset("a3")})
        events = scan(gr, conn, accounts=[im])
        assert [(r.action, r.gramps_id, r.title, r.detail) for r in items(events)] == [
            ("failed", "ABC123", "Gone", "Immich asset a1 is gone"),
            ("failed", "DEF456", "Trashed", "Immich asset a2 is in the trash")]
        assert events[-1].data["attention"] == 2

    def test_the_source_gramps_names_is_the_one_checked(self, conn):
        mint(conn, "ABC123", "a1")
        mint(conn, "DEF456", "a2")
        reserve(conn, "GHJ789")
        gr = FakeGramps(media={"ABC123": media("ABC123", desc="Moved", immich="a9"),
                               "DEF456": media("DEF456", desc="Moved away", immich="a8"),
                               "GHJ789": media("GHJ789", desc="Taken", immich="a7"),
                               "KMN234": media("KMN234", desc="New", immich="a6")})
        im = CountingImmich(assets={"a2": asset("a2"), "a9": asset("a9")})
        events = scan(gr, conn, accounts=[im])
        assert im.requested == [["a9", "a8", "a7"]]
        assert [(r.gramps_id, r.title, r.detail) for r in items(events) if r.action == "failed"] == [
            ("DEF456", "Moved away", "Immich asset a8 is gone"), ("GHJ789", "Taken", "Immich asset a7 is gone")]
        assert events[-1].data["attention"] == 2

    def test_shared_assets_are_asked_for_once(self, conn):
        mint(conn, "ABC123", "a1")
        mint(conn, "DEF456", "a1")
        gr = FakeGramps(media={"ABC123": media("ABC123", immich="a1"), "DEF456": media("DEF456", immich="a1")})
        im = CountingImmich()
        events = scan(gr, conn, accounts=[im])
        assert im.requested == [["a1"]]
        assert [r.gramps_id for r in items(events)] == ["ABC123", "DEF456"]

    def test_a_gone_paperless_document_needs_attention(self, conn):
        mint(conn, "ABC123", "7", system="paperless")
        mint(conn, "DEF456", "8", system="paperless")
        gr = FakeGramps(media={"ABC123": media("ABC123", desc="Deed", paperless="7"),
                               "DEF456": media("DEF456", paperless="8")})
        events = scan(gr, conn, paperless=FakePaperless({8}))
        assert [(r.action, r.gramps_id, r.title, r.detail) for r in items(events)] == [
            ("failed", "ABC123", "Deed", "Paperless document 7 is gone")]
        assert events[-1].data["attention"] == 1

    def test_without_the_services_nothing_is_checked_there(self, conn):
        mint(conn, "ABC123", "a1")
        mint(conn, "DEF456", "7", system="paperless")
        gr = FakeGramps(media={"ABC123": media("ABC123", immich="a1"), "DEF456": media("DEF456", paperless="7")})
        events = scan(gr, conn)
        assert items(events) == [] and events[-1].data["attention"] == 0

    def test_gramps_unreadable_stops_the_scan(self, conn):
        mint(conn, "ABC123", "a1")
        events = scan(DownGramps(), conn, paperless=FakePaperless(), accounts=[FakeImmich()])
        assert [e.kind for e in events] == ["error", "summary"]
        assert events[0].detail == "Gramps could not be read, nothing checked: gramps down"
        assert events[1].data == {"registered": 0, "repointed": 0, "withdrawn": 0, "attention": 0, "errors": 0}


class TestApply:
    def _world(self, conn):
        mint(conn, "ABC123", "a1")
        mint(conn, "DEF456", "a2")
        reserve(conn, "GHJ789")
        gr = FakeGramps(media={"ABC123": media("ABC123", immich="a9"),
                               "GHJ789": media("GHJ789", immich="a3"),
                               "KMN234": media("KMN234", desc="New", immich="a4"),
                               "PQR567": media("PQR567", desc="Manual")})
        return gr

    def test_registers_repoints_and_withdraws(self, conn):
        gr = self._world(conn)
        events = scan(gr, conn, apply=True)
        assert sorted((r.action, r.gramps_id) for r in items(events)) == [
            ("created", "KMN234"), ("created", "PQR567"), ("updated", "ABC123"), ("updated", "DEF456"),
            ("updated", "GHJ789")]
        assert events[-1].data == {"registered": 2, "repointed": 2, "withdrawn": 1, "attention": 0, "errors": 0}
        new = row(conn, "KMN234")
        assert (new["source_system"], new["source_id"]) == ("immich", "a4")
        assert new["created_at"] and new["minted_at"] == new["created_at"] and new["withdrawn_at"] is None
        manual = row(conn, "PQR567")
        assert (manual["source_system"], manual["source_id"], manual["minted_at"]) == (None, None, None)
        assert manual["created_at"]
        moved = row(conn, "ABC123")
        assert (moved["source_id"], moved["minted_at"], moved["withdrawn_at"]) == ("a9", "2026-01-01", None)
        taken = row(conn, "GHJ789")
        assert (taken["source_system"], taken["source_id"]) == ("immich", "a3")
        assert taken["minted_at"] and taken["created_at"] == "2026-01-01"
        gone = row(conn, "DEF456")
        assert gone["withdrawn_at"] and gone["withdrawn_reason"] == reconcile.DELETED_REASON
        assert (gone["source_system"], gone["source_id"]) == ("immich", "a2")

    def test_a_second_apply_is_quiet(self, conn):
        gr = self._world(conn)
        scan(gr, conn, apply=True)
        before = live_rows(conn)
        events = scan(gr, conn, apply=True)
        assert items(events) == [] and live_rows(conn) == before
        assert events[-1].data == {"registered": 0, "repointed": 0, "withdrawn": 0, "attention": 0, "errors": 0}

    def test_selected_limits_the_apply(self, conn):
        gr = self._world(conn)
        events = scan(gr, conn, apply=True, selected={"media:KMN234", "media:DEF456"})
        assert sorted((r.action, r.gramps_id) for r in items(events)) == [
            ("created", "KMN234"), ("updated", "DEF456"), ("would_create", "PQR567"),
            ("would_update", "ABC123"), ("would_update", "GHJ789")]
        assert events[-1].data == {"registered": 1, "repointed": 0, "withdrawn": 1, "attention": 0, "errors": 0}
        assert row(conn, "PQR567") is None
        assert row(conn, "ABC123")["source_id"] == "a1"
        assert row(conn, "GHJ789")["source_system"] is None
        assert row(conn, "DEF456")["withdrawn_at"]

    def test_preview_writes_nothing(self, conn):
        gr = self._world(conn)
        before = [dict(r) for r in conn.execute("SELECT * FROM minted_media ORDER BY gramps_id")]
        events = scan(gr, conn, apply=False)
        assert {r.action for r in items(events)} == {"would_create", "would_update"}
        assert [dict(r) for r in conn.execute("SELECT * FROM minted_media ORDER BY gramps_id")] == before
        assert events[-1].data == {"registered": 0, "repointed": 0, "withdrawn": 0, "attention": 0, "errors": 0}

    def test_an_unreachable_paperless_is_an_error_while_the_rest_runs(self, conn):
        mint(conn, "ABC123", "7", system="paperless")
        mint(conn, "DEF456", "a1")
        gr = FakeGramps(media={"ABC123": media("ABC123", paperless="7"), "DEF456": media("DEF456", immich="a1"),
                               "GHJ789": media("GHJ789", desc="New", immich="a2")})
        events = scan(gr, conn, paperless=FakePaperless(down=True), accounts=[FakeImmich()], apply=True)
        errors = [e for e in events if e.kind == "error"]
        assert [e.detail for e in errors] == ["Paperless: paperless down; its records were not checked"]
        assert [(r.action, r.gramps_id) for r in items(events)] == [("created", "GHJ789"), ("failed", "DEF456")]
        assert events[-1].data == {"registered": 1, "repointed": 0, "withdrawn": 0, "attention": 1, "errors": 1}

    def test_an_unreachable_immich_is_an_error_too(self, conn):
        mint(conn, "ABC123", "a1")
        events = scan(FakeGramps(media={"ABC123": media("ABC123", immich="a1")}), conn, accounts=[DownImmich()])
        assert [e.detail for e in events if e.kind == "error"] == ["Immich: immich down; its records were not checked"]
        assert items(events) == [] and events[-1].data["errors"] == 1

    def test_started_counts_gramps_and_the_ledger(self, conn):
        ledger = conn.execute("SELECT COUNT(*) FROM minted_media").fetchone()[0]
        gr = self._world(conn)
        events = scan(gr, conn)
        assert events[0].kind == "started"
        assert events[0].detail == f"4 media in Gramps, {ledger + 3} codes in the ledger"

    def test_progress_events_bracket_the_scan(self, conn):
        gr = self._world(conn)
        events = scan(gr, conn, accounts=[FakeImmich(assets={"a9": asset("a9"), "a3": asset("a3")})])
        progress = [e for e in events if e.kind == "progress"]
        dones = [p.data["done"] for p in progress]
        assert dones[0] == 0 and dones == sorted(dones)
        assert len({p.data["total"] for p in progress}) == 1
        assert dones[-1] == progress[-1].data["total"] and progress[-1].data["percent"] == 100
        assert [p.detail for p in progress][-1] == "Checking Immich and Paperless"
        assert events.index(progress[-1]) < events.index(events[-1])

    def test_an_empty_world_still_closes_the_progress(self, conn):
        events = scan(FakeGramps(), conn)
        progress = [e for e in events if e.kind == "progress"]
        assert progress[-1].data["done"] == progress[-1].data["total"]
        assert events[-1].kind == "summary"
