import asyncio
import csv

import pytest

from bifrost.core import db
from bifrost.modules import photos_handover as ho
from bifrost.modules import sync_immich
from bifrost.web.runs import record_run
from test_photos import CFG, VersionsImmich, gdate, media, note, place, stacked, tagged
from test_sync_immich import FakeGramps, mint


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(ho, "UNTAG_PAUSE", 0)
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


def collect(gen):
    async def go():
        return [e async for e in gen]
    return asyncio.run(go())


def recorded(conn, job, gen):
    return asyncio.run(record_run(conn, job, gen))


def summary(events):
    return next(e for e in events if e.kind == "summary")


def items(events, entity=None):
    return [e for e in events if e.kind == "item" and (entity is None or e.entity == entity)]


def rows_of(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def keep_row(row, action):
    conn_row = dict(row)
    conn_row["keep"] = "" if action is None else action
    return conn_row


def write_rows(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ho.CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)


def world(conn):
    """Two registered photos: ABC123 disagrees with Immich on title, date and place; DEF456 agrees"""
    mint(conn, "ABC123", "a1")
    mint(conn, "DEF456", "b1")
    a = tagged("a1", "ID/ABC123", "Sync/Date", "Date/Year", "Place/P0002", desc="Immich title",
               when="1945-06-15T12:00:00Z")
    b = tagged("b1", "ID/DEF456", desc="Same")
    for x in (a, b):
        x.update({"width": 100, "height": 80, "ownerId": "me-1"})
    im = VersionsImmich(assets={"a1": a, "b1": b})
    gr = FakeGramps({"ABC123": media(desc="Gramps title", date=gdate(0, 0, 1923)),
                     "DEF456": media("DEF456", "h2", "Same", attribute_list=[sync_immich._attr("Immich ID", "b1")])},
                    places=[place(holding=("h1",)), place("P0002", "Taylors Falls")])
    return im, gr


class TestDryRun:
    def test_refuses_while_a_sync_is_pending(self, conn, tmp_path):
        im, gr = world(conn)
        im.assets["a1"]["originalPath"] = "/up/moved.jpg"
        events = collect(ho.dry_run(gr, [im], conn, CFG, tmp_path / "d.csv"))
        failed = items(events)
        assert [e.action for e in failed] == ["failed"] and failed[0].gramps_id == "ABC123"
        assert "pending sync changes: file" in failed[0].detail
        assert summary(events).data == {"blocked": 1} and summary(events).detail == "run Sync first"
        assert not (tmp_path / "d.csv").exists()

    def test_a_register_row_without_its_media_is_reported_not_blocking(self, conn, tmp_path):
        im, gr = world(conn)
        del gr.media["DEF456"]
        events = collect(ho.dry_run(gr, [im], conn, CFG, tmp_path / "d.csv"))
        assert [e.detail for e in items(events) if e.action == "failed"] == [
            "the register points at DEF456, which is not in Gramps"]
        assert "blocked" not in summary(events).data

    def test_writes_the_decisions_and_the_plan(self, conn, tmp_path):
        im, gr = world(conn)
        conn.execute("INSERT INTO photo_notes (asset_id, gramps_id, text, updated_at) VALUES ('a1', 'ABC123', 'A note', 't')")
        conn.execute("INSERT INTO photo_notes (asset_id, text, updated_at) VALUES ('b1', 'https://only.example/y', 't')")
        conn.execute("INSERT INTO photo_links (asset_id, url, added_at) VALUES ('a1', 'https://kept.example/x', 't')")
        conn.execute("INSERT INTO photo_links (asset_id, url, added_at) VALUES ('zz', 'https://waiting.example/z', 't')")
        conn.commit()
        out = tmp_path / "d.csv"
        run_id, events = recorded(conn, "photos.handover.dry-run", ho.dry_run(gr, [im], conn, CFG, out))
        assert conn.execute("SELECT job, status FROM runs WHERE id=?", (run_id,)).fetchone()[:] == (
            "photos.handover.dry-run", "ok")
        rows = rows_of(out)
        assert [(r["gramps_id"], r["field"], r["gramps_value"], r["immich_value"], r["keep"]) for r in rows] == [
            ("ABC123", "title", "Gramps title", "Immich title", ""),
            ("ABC123", "date", "1923", "1945", ""),
            ("ABC123", "place", "P0001", "P0002", "")]
        assert summary(events).data == {"disagreements": 3, "notes": 1, "url_notes": 1, "note_choices": 0,
                                        "links": 1, "links_waiting": 1, "rows": 3, "csv": str(out)}
        assert gr.updated == [] and gr.updated_places == [] and im.updated_assets == []

    def test_near_duplicate_notes_become_a_choice(self, conn, tmp_path):
        im, gr = world(conn)
        gr.media["ABC123"]["desc"] = "Immich title"
        im.assets["a1"]["tags"] = [{"value": "ID/ABC123"}]
        conn.executemany("INSERT INTO photo_notes (asset_id, gramps_id, text, updated_at) VALUES (?, ?, ?, ?)",
                         [("a1", "ABC123", "Version one of the note", "2026-01-02"),
                          ("old-main", "ABC123", "Version one of the note, older", "2026-01-01")])
        conn.commit()
        out = tmp_path / "d.csv"
        events = collect(ho.dry_run(gr, [im], conn, CFG, out))
        rows = rows_of(out)
        assert [(r["gramps_id"], r["asset_id"], r["field"], r["immich_value"]) for r in rows] == [
            ("ABC123", "a1", "note", "Version one of the note"),
            ("ABC123", "old-main", "note", "Version one of the note, older")]
        assert summary(events).data["note_choices"] == 2 and summary(events).data["notes"] == 0
        assert "2 note rows" in items(events, "note")[0].detail


class TestApply:
    def _decided(self, conn, tmp_path, keep):
        im, gr = world(conn)
        out = tmp_path / "d.csv"
        collect(ho.dry_run(gr, [im], conn, CFG, out))
        write_rows(out, [keep_row(r, keep.get(r["field"])) for r in rows_of(out)])
        return im, gr, out

    def test_blank_keep_means_gramps_wins(self, conn, tmp_path):
        im, gr, out = self._decided(conn, tmp_path, {})
        events = collect(ho.apply(gr, [im], conn, CFG, out))
        assert gr.updated == [] and gr.updated_places == []
        assert gr.media["ABC123"]["desc"] == "Gramps title"
        assert summary(events).data == {"titles": 0, "dates": 0, "places": 0, "notes": 0, "links": 0,
                                        "errors": 0, "links_waiting": 0}

    def test_keep_immich_rows_are_applied_once(self, conn, tmp_path):
        im, gr, out = self._decided(conn, tmp_path, {"title": "immich", "date": "Immich", "place": "immich"})
        run_id, events = recorded(conn, "photos.handover.apply", ho.apply(gr, [im], conn, CFG, out))
        saved = gr.media["ABC123"]
        assert saved["desc"] == "Immich title"
        assert saved["date"] == gdate(0, 0, 1945)
        assert gr.places[0]["media_list"] == [] and gr.places[1]["media_list"][0]["ref"] == "h1"
        assert [e.action for e in items(events, "media")] == ["updated"]
        assert items(events, "media")[0].data["cols"] == {"title": "Immich title", "date": "1945"}
        assert items(events, "place")[0].data["cols"] == {"place": "Taylors Falls"}
        assert summary(events).data["titles"] == 1 and summary(events).data["places"] == 1
        assert conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()[0] == "ok"
        again = collect(ho.apply(gr, [im], conn, CFG, out))
        assert items(again) == [] and len(gr.updated) == 1 and len(gr.updated_places) == 2

    def test_notes_and_links_go_to_the_media(self, conn, tmp_path):
        im, gr, out = self._decided(conn, tmp_path, {})
        gr.notes["n-0"] = note("n-0", "Already there")
        gr.media["ABC123"]["note_list"] = ["n-0"]
        conn.execute("INSERT INTO photo_notes (asset_id, gramps_id, text, updated_at) VALUES ('a1', 'ABC123', 'A note', 't')")
        conn.execute("INSERT INTO photo_notes (asset_id, text, updated_at) VALUES ('b1', 'https://only.example/y', 't')")
        conn.execute("INSERT INTO photo_links (asset_id, url, added_at) VALUES ('a1', 'https://kept.example/x', 't')")
        conn.execute("INSERT INTO photo_links (asset_id, url, added_at) VALUES ('zz', 'https://waiting.example/z', 't')")
        conn.commit()
        events = collect(ho.apply(gr, [im], conn, CFG, out))
        assert gr.notes["n-0"]["text"]["string"] == "Already there\n\nA note"
        assert len(gr.notes) == 1
        assert sync_immich.media_links(gr.media["ABC123"]) == ["https://kept.example/x"]
        assert sync_immich.media_links(gr.media["DEF456"]) == ["https://only.example/y"]
        data = summary(events).data
        assert (data["notes"], data["links"], data["links_waiting"], data["errors"]) == (1, 2, 1, 0)
        assert conn.execute("SELECT COUNT(*) FROM photo_notes").fetchone()[0] == 2
        again = collect(ho.apply(gr, [im], conn, CFG, out))
        assert items(again) == [] and gr.notes["n-0"]["text"]["string"] == "Already there\n\nA note"

    def test_a_note_choice_writes_only_the_picked_row(self, conn, tmp_path):
        im, gr = world(conn)
        conn.executemany("INSERT INTO photo_notes (asset_id, gramps_id, text, updated_at) VALUES (?, ?, ?, ?)",
                         [("a1", "ABC123", "Newer", "2026-01-02"), ("old-main", "ABC123", "Older", "2026-01-01")])
        conn.commit()
        out = tmp_path / "d.csv"
        collect(ho.dry_run(gr, [im], conn, CFG, out))
        write_rows(out, [keep_row(r, "immich" if r["asset_id"] == "old-main" else None) for r in rows_of(out)])
        collect(ho.apply(gr, [im], conn, CFG, out))
        assert [n["text"]["string"] for n in gr.notes.values()] == ["Older"]

    def test_a_photo_in_several_galleries_keeps_them(self, conn, tmp_path):
        im, gr, out = self._decided(conn, tmp_path, {"place": "immich"})
        gr.places[1]["media_list"].append(sync_immich._media_ref("h1"))
        events = collect(ho.apply(gr, [im], conn, CFG, out))
        assert gr.updated_places == []
        assert [e.detail for e in items(events, "place")] == ["in more than one gallery, left alone"]
        assert summary(events).data["errors"] == 1

    def test_a_csv_without_the_columns_is_refused(self, conn, tmp_path):
        im, gr = world(conn)
        out = tmp_path / "d.csv"
        out.write_text("gramps_id,keep\nABC123,immich\n")
        with pytest.raises(sync_immich.SyncError, match="lacks the columns"):
            collect(ho.apply(gr, [im], conn, CFG, out))


class TestCleanupTags:
    def test_removes_bifrosts_date_place_and_field_tags_through_the_owner(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "ID/ABC123", "Sync/Gramps", "Sync/ManualFaces", "Sync/Description", "Sync/Date",
                   "Sync/Note", "Sync/Location", "Date/Year", "Date/Estimated", "Date/Span/-10+5",
                   "Place/P0001", "Holiday/1923", "Date/Wrong")
        v = tagged("v1", "Date/Month", "ID/ABC123")
        for x in (a, v):
            x.update({"width": 100, "height": 80, "ownerId": "me-1"})
        im = VersionsImmich(assets={"a1": a, "v1": v})
        stacked(im, "a1", "v1")
        run_id, events = recorded(conn, "photos.handover.cleanup", ho.cleanup_tags([im], conn, CFG))
        assert sorted(t["value"] for t in a["tags"]) == [
            "Date/Wrong", "Holiday/1923", "ID/ABC123", "Sync/Gramps", "Sync/ManualFaces"]
        assert sorted(t["value"] for t in v["tags"]) == ["ID/ABC123"]
        assert im.upserted == []
        assert summary(events).data == {"cleaned": 2, "skipped": 0, "put_back": 0, "errors": 0}
        assert conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()[0] == "ok"
        again = collect(ho.cleanup_tags([im], conn, CFG))
        assert summary(again).data == {"cleaned": 0, "skipped": 2, "put_back": 0, "errors": 0}

    def test_a_kept_tag_immich_drops_is_put_back(self, conn):
        class DroppingImmich(VersionsImmich):
            async def untag_asset(self, tag_id, asset_id):
                await super().untag_asset(tag_id, asset_id)
                self.assets[asset_id]["tags"] = [t for t in self.assets[asset_id]["tags"]
                                                 if t["value"] != "Sync/Gramps"]

        mint(conn, "ABC123", "a1")
        a = tagged("a1", "ID/ABC123", "Sync/Gramps", "Date/Year")
        a.update({"ownerId": "me-1"})
        im = DroppingImmich(assets={"a1": a})
        events = collect(ho.cleanup_tags([im], conn, CFG))
        assert sorted(t["value"] for t in a["tags"]) == ["ID/ABC123", "Sync/Gramps"]
        assert [e.detail for e in items(events)] == ["removed date/year",
                                                     "put back sync/gramps, which Immich had dropped"]
        assert summary(events).data["put_back"] == 1

    def test_an_asset_without_a_known_owner_is_skipped(self, conn):
        mint(conn, "ABC123", "a1")
        a = tagged("a1", "Date/Year")
        a[sync_immich._OWNER_TAGS_KEY] = None
        im = VersionsImmich(assets={"a1": a})
        events = collect(ho.cleanup_tags([im], conn, CFG))
        assert [e.detail for e in items(events)] == ["cannot tell which account owns this asset"]
        assert sorted(t["value"] for t in a["tags"]) == ["Date/Year"]

    def test_photos_not_in_gramps_are_left_alone(self, conn):
        a = tagged("a1", "Date/Year", "Sync/Date")
        im = VersionsImmich(assets={"a1": a})
        events = collect(ho.cleanup_tags([im], conn, CFG))
        assert items(events) == [] and len(a["tags"]) == 2
