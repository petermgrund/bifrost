import asyncio

import pytest

from bifrost.core import db
from bifrost.core.clients.immich import ImmichError
from bifrost.modules import faces
from test_sync_immich import FakeGramps, FakeImmich, asset


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


class TestLinkCrud:
    def test_set_list_delete(self, conn):
        faces.set_link(conn, "h1", "uuid-1", "Ed")
        faces.set_link(conn, "h2", "uuid-2")
        links = faces.list_links(conn)
        assert [(l["gramps_handle"], l["immich_person_id"], l["label"])
                for l in links] == [("h2", "uuid-2", ""), ("h1", "uuid-1", "Ed")]
        assert faces.delete_link(conn, "h1") is True
        assert faces.delete_link(conn, "h1") is False
        assert len(faces.list_links(conn)) == 1

    def test_relink_replaces_both_sides(self, conn):
        faces.set_link(conn, "h1", "uuid-1", "Ed")
        faces.set_link(conn, "h1", "uuid-2", "Ed again")
        links = faces.list_links(conn)
        assert len(links) == 1 and links[0]["immich_person_id"] == "uuid-2"
        faces.set_link(conn, "h9", "uuid-2", "Stolen")
        links = faces.list_links(conn)
        assert len(links) == 1 and links[0]["gramps_handle"] == "h9"

    def test_owner_column_round_trips(self, conn):
        faces.set_link(conn, "H1", "P1", "Ed", owner_user_id="acct-a")
        row = faces.list_links(conn)[0]
        assert row["owner_user_id"] == "acct-a"

    def test_two_links_per_person_across_accounts(self, conn):
        faces.set_link(conn, "H1", "P1", owner_user_id="acct-a")
        faces.set_link(conn, "H1", "P2", owner_user_id="acct-b")
        rows = faces.list_links(conn)
        assert {r["immich_person_id"] for r in rows} == {"P1", "P2"}

    def test_same_account_relink_replaces(self, conn):
        faces.set_link(conn, "H1", "P1", owner_user_id="acct-a")
        faces.set_link(conn, "H1", "P3", owner_user_id="acct-a")
        rows = faces.list_links(conn)
        assert [r["immich_person_id"] for r in rows] == ["P3"]

    def test_immich_person_unique_across_gramps_people(self, conn):
        faces.set_link(conn, "H1", "P1", owner_user_id="acct-a")
        faces.set_link(conn, "H2", "P1", owner_user_id="acct-a")
        rows = faces.list_links(conn)
        assert len(rows) == 1 and rows[0]["gramps_handle"] == "H2"

    def test_no_owner_keeps_legacy_replace_semantics(self, conn):
        faces.set_link(conn, "H1", "P1", owner_user_id="acct-a")
        faces.set_link(conn, "H1", "P2")
        rows = faces.list_links(conn)
        assert [r["immich_person_id"] for r in rows] == ["P2"]

    def test_owned_relink_also_replaces_null_owner_rows(self, conn):
        # a legacy row of unknown account must not survive a definite relink
        faces.set_link(conn, "H1", "P1")
        faces.set_link(conn, "H1", "P2", owner_user_id="acct-a")
        rows = faces.list_links(conn)
        assert [r["immich_person_id"] for r in rows] == ["P2"]


class TestYamlImport:
    def test_imports_once(self, conn, tmp_path):
        p = tmp_path / "person_map.yaml"
        p.write_text(
            "people:\n"
            "- gramps_handle: h1\n"
            "  immich_person_id: uuid-1\n"
            "  label: Ed\n"
            "- gramps_handle: h2\n"
            "  immich_person_id: uuid-2\n"
            "- immich_person_id: no-handle-skipped\n")
        assert faces.import_person_map_yaml(conn, p) == 2
        # table now non-empty: a second import is a no-op
        assert faces.import_person_map_yaml(conn, p) == 0
        assert len(faces.list_links(conn)) == 2

    def test_missing_file(self, conn, tmp_path):
        assert faces.import_person_map_yaml(conn, tmp_path / "nope.yaml") == 0
        assert faces.import_person_map_yaml(conn, None) == 0


class BackfillImmich(FakeImmich):
    async def get_assets_many(self, asset_ids, concurrency=8):
        return {i: self.assets.get(i) for i in asset_ids}


class BackfillGramps(FakeGramps):
    async def list_media(self):
        return list(self.media.values())


def _mint(conn, gid, aid):
    conn.execute(
        "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
        "VALUES (?, 'immich', ?, 't', 't')", (gid, aid))
    conn.commit()


def _run(gramps, immich, conn, apply, selected=None):
    async def collect():
        return [e async for e in faces.apply_links(
            gramps, [immich], conn, apply=apply, selected=selected)]
    return asyncio.run(collect())


def _items(events):
    return [e for e in events if e.kind == "item"]


class ResolvingImmich(BackfillImmich):
    """Adds the listing and person endpoints resolution needs"""

    def __init__(self, me_id, label, people=None, listed=None, **kw):
        super().__init__(me_id=me_id, **kw)
        self.label = label
        self._people = people or {}      # id -> name (direct GET universe)
        self._listed = listed if listed is not None else list(self._people)
        self.thumb_requests = []

    async def list_people(self, with_hidden=True):
        return [{"id": pid, "name": self._people[pid], "isHidden": False}
                for pid in self._listed]

    async def get_person(self, person_id):
        if person_id in self._people:
            return {"id": person_id, "name": self._people[person_id]}
        raise ImmichError(404, "no person")

    async def person_thumbnail(self, person_id):
        self.thumb_requests.append(person_id)
        if person_id in self._people:
            return b"img", "image/jpeg"
        raise ImmichError(404, "no thumbnail")


class TestResolution:
    def test_merged_people_carries_account(self, conn):
        a = ResolvingImmich("ua", "fh", people={"p1": "Astrid"})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed"})
        people = asyncio.run(faces.merged_people([a, b]))
        assert {(p["id"], p["account_label"]) for p in people} == {
            ("p1", "fh"), ("p2", "peter")}

    def test_padded_immich_names_are_trimmed(self, conn):
        faces.set_link(conn, "H1", "p2", "")
        a = ResolvingImmich("ua", "fh", people={"p1": " Ada Berg "})
        b = ResolvingImmich("ub", "peter", people={"p2": "Bo Lindqvist "})
        people = asyncio.run(faces.merged_people([a, b]))
        assert sorted(p["name"] for p in people) == ["Ada Berg", "Bo Lindqvist"]
        rows = asyncio.run(faces.enrich_links([a, b], conn))
        assert rows[0]["person_name"] == "Bo Lindqvist"
        assert asyncio.run(faces.resolve_person([a, b], "p1"))["name"] == "Ada Berg"

    def test_enrich_resolves_via_listing_and_backfills_owner(self, conn):
        faces.set_link(conn, "H1", "p2", "Ed")   # legacy row, no owner
        a = ResolvingImmich("ua", "fh", people={"p1": "Astrid"})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed"})
        rows = asyncio.run(faces.enrich_links([a, b], conn))
        assert rows[0]["person_name"] == "Ed"
        assert rows[0]["account_label"] == "peter"
        assert faces.list_links(conn)[0]["owner_user_id"] == "ub"

    def test_enrich_falls_back_to_direct_get_when_listing_omits(self, conn):
        faces.set_link(conn, "H1", "p9", "Hidden")
        b = ResolvingImmich("ub", "peter", people={"p9": "Eleraine"}, listed=[])
        rows = asyncio.run(faces.enrich_links([b], conn))
        assert rows[0]["person_name"] == "Eleraine"
        assert rows[0]["resolved"] is True
        assert faces.list_links(conn)[0]["owner_user_id"] == "ub"

    def test_enrich_marks_unresolvable(self, conn):
        faces.set_link(conn, "H1", "gone", "Ghost")
        b = ResolvingImmich("ub", "peter", people={})
        rows = asyncio.run(faces.enrich_links([b], conn))
        assert rows[0]["resolved"] is False
        assert faces.list_links(conn)[0]["owner_user_id"] is None

    def test_grouped_links_one_row_per_gramps_person(self, conn):
        faces.set_link(conn, "H1", "p1", "Ed", owner_user_id="ua")
        faces.set_link(conn, "H1", "p2", "Ed", owner_user_id="ub")
        faces.set_link(conn, "H2", "p3", "Astrid", owner_user_id="ua")
        a = ResolvingImmich("ua", "fh", people={"p1": "Ed G", "p3": "Astrid B"})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed Grund"})
        groups = asyncio.run(faces.grouped_links([a, b], conn))
        assert [g["gramps_handle"] for g in groups] == ["H2", "H1"]
        h1 = next(g for g in groups if g["gramps_handle"] == "H1")
        assert h1["label"] == "Ed"
        assert [(l["person_name"], l["account_label"]) for l in h1["links"]] == [
            ("Ed G", "fh"), ("Ed Grund", "peter")]

    def test_grouped_links_label_falls_back_to_person_name(self, conn):
        faces.set_link(conn, "H1", "p2", "", owner_user_id="ub")
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed Grund"})
        groups = asyncio.run(faces.grouped_links([b], conn))
        assert groups[0]["label"] == "Ed Grund"

    def test_listing_degrades_when_one_account_is_down(self, conn):
        class DownImmich(ResolvingImmich):
            async def get_me(self):
                raise ImmichError(500, "down")

            async def list_people(self, with_hidden=True):
                raise ImmichError(500, "down")

        faces.set_link(conn, "H1", "p2", "Ed")
        down = DownImmich("ua", "fh")
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed Grund"})
        people = asyncio.run(faces.merged_people([down, b]))
        assert [(p["id"], p["account_label"]) for p in people] == [("p2", "peter")]
        rows = asyncio.run(faces.enrich_links([down, b], conn))
        assert rows[0]["person_name"] == "Ed Grund" and rows[0]["resolved"]

    def test_resolve_person_survives_broken_get_me_without_backfill(self, conn):
        class NoMe(ResolvingImmich):
            async def get_me(self):
                raise ImmichError(500, "down")

        faces.set_link(conn, "H1", "p2", "Ed")
        b = NoMe("ub", "peter", people={"p2": "Ed Grund"})
        rows = asyncio.run(faces.enrich_links([b], conn))
        assert rows[0]["resolved"] is True
        # owner unknown: the legacy row must stay unannotated, not get ""
        assert faces.list_links(conn)[0]["owner_user_id"] is None

    def test_thumbnail_prefers_the_owning_account(self, conn):
        faces.set_link(conn, "H1", "p2", "Ed", owner_user_id="ub")
        a = ResolvingImmich("ua", "fh", people={"p2": "Shadow Ed"})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed Grund"})
        content, mime = asyncio.run(
            faces.person_thumbnail_bytes([a, b], conn, "p2"))
        assert b.thumb_requests == ["p2"]
        assert a.thumb_requests == []

    def test_thumbnail_falls_back_across_accounts(self, conn):
        a = ResolvingImmich("ua", "fh", people={})
        b = ResolvingImmich("ub", "peter", people={"p9": "Eleraine"})
        content, mime = asyncio.run(
            faces.person_thumbnail_bytes([a, b], conn, "p9"))
        assert content == b"img" and b.thumb_requests == ["p9"]

    def test_thumbnail_mixed_errors_raise_the_hard_error(self, conn):
        class Down(ResolvingImmich):
            async def person_thumbnail(self, person_id):
                raise ImmichError(0, "request failed")

        a = ResolvingImmich("ua", "fh", people={})
        down = Down("ub", "peter")
        with pytest.raises(ImmichError) as exc:
            asyncio.run(faces.person_thumbnail_bytes([a, down], conn, "p9"))
        assert exc.value.status not in (400, 404)

    def test_resolve_person_probes_accounts_in_order(self, conn):
        a = ResolvingImmich("ua", "fh", people={})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed"}, listed=[])
        info = asyncio.run(faces.resolve_person([a, b], "p2"))
        assert info == {"name": "Ed", "owner_user_id": "ub",
                        "account_label": "peter"}
        assert asyncio.run(faces.resolve_person([a], "p2")) is None


class TestBackfill:
    def _world(self, conn):
        faces.set_link(conn, "h-ed", "uuid-ed", "Ed")
        _mint(conn, "K1", "a1")
        im = BackfillImmich(
            assets={"a1": asset("a1")},
            faces={"a1": [{"person": {"id": "uuid-ed", "name": "Ed"}}]})
        gr = BackfillGramps(
            media={"K1": {"gramps_id": "K1", "handle": "mh1"}},
            people={"h-ed": {"handle": "h-ed", "media_list": []}})
        return im, gr

    def test_preview_writes_nothing(self, conn):
        im, gr = self._world(conn)
        events = _run(gr, im, conn, apply=False)
        rows = _items(events)
        assert len(rows) == 1
        assert rows[0].action == "would_create" and rows[0].entity == "face"
        assert rows[0].source_id == "a1" and rows[0].gramps_id == "K1"
        assert rows[0].title and rows[0].title != "Ed"
        assert rows[0].data == {"cols": {"Ed": "link"}}
        assert gr.updated_people == []
        summary = events[-1]
        assert summary.kind == "summary" and summary.data["faces_linked"] == 1

    def test_row_title_is_the_gramps_media_desc(self, conn):
        im, gr = self._world(conn)
        gr.media["K1"]["desc"] = "Ed at the lake"
        rows = _items(_run(gr, im, conn, apply=False))
        assert rows[0].title == "Ed at the lake"

    def test_progress_events_bracket_the_scan(self, conn):
        im, gr = self._world(conn)
        events = _run(gr, im, conn, apply=False)
        progress = [e for e in events if e.kind == "progress"]
        assert progress and progress[0].data["done"] == 0
        assert progress[-1].data["done"] == progress[-1].data["total"] == 1

    def test_selected_limits_an_apply(self, conn):
        im, gr = self._world(conn)
        _mint(conn, "K2", "a2")
        im.assets["a2"] = asset("a2")
        im.faces["a2"] = [{"person": {"id": "uuid-ed", "name": "Ed"}}]
        gr.media["K2"] = {"gramps_id": "K2", "handle": "mh2"}
        events = _run(gr, im, conn, apply=True, selected={"face:a2"})
        assert [e.source_id for e in _items(events)] == ["a2"]
        assert [p["media_list"][0]["ref"] for p in gr.updated_people] == ["mh2"]
        assert im.faces_requested == ["a2"]

    def test_apply_links_face(self, conn):
        im, gr = self._world(conn)
        events = _run(gr, im, conn, apply=True)
        assert [e for e in events if e.action == "created"]
        assert gr.updated_people[0]["media_list"][0]["ref"] == "mh1"
        # second run ref exists, rect-less face box has no rect to add
        gr.updated_people.clear()
        events = _run(gr, im, conn, apply=True)
        assert not [e for e in events if e.action == "created"]
        assert gr.updated_people == []

    def test_no_links_errors(self, conn):
        im, gr = self._world(conn)
        conn.execute("DELETE FROM person_links")
        conn.commit()
        events = _run(gr, im, conn, apply=True)
        assert events[0].kind == "error"
        assert events[-1].kind == "summary"

    def test_unreadable_asset_counted(self, conn):
        im, gr = self._world(conn)
        _mint(conn, "K2", "a2")  # asset a2 unknown to Immich
        events = _run(gr, im, conn, apply=True)
        summary = events[-1]
        assert summary.data["unreadable"] == 1
        assert summary.data["faces_linked"] == 1
