import asyncio

import pytest

from bifrost.core import db
from bifrost.core.clients.gramps import GrampsError
from bifrost.core.clients.immich import ImmichError
from bifrost.modules import faces

from test_sync_immich import FakeGramps, FakeImmich, asset, linked, mint


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


def run(coro):
    return asyncio.run(coro)


def named(handle, first, surname, *person_ids, gramps_id="I0001", media_list=()):
    """A linked Gramps person with a display name"""
    return {**linked(handle, *person_ids, media_list=media_list), "gramps_id": gramps_id,
            "primary_name": {"first_name": first, "surname_list": [{"surname": surname}]}}


def table_exists(conn, name):
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


class TestPeopleIndex:
    def test_person_ids_reads_the_attribute(self):
        person = linked("h1", "p1", " p2 ", "  ")
        person["attribute_list"].append({"type": "Nickname", "value": "Ed"})
        assert faces.person_ids(person) == ["p1", "p2"]
        assert faces.person_ids({"handle": "h2"}) == []

    def test_rows_sorted_by_name_with_counts(self):
        ed = named("h-ed", "Ed", "Grund", "p1", "p2", gramps_id="I0002",
                   media_list=[{"ref": "m1", "rect": [1, 2, 3, 4]}, {"ref": "m2", "rect": []}])
        astrid = named("h-as", "Astrid", "Berg", gramps_id="I0001")
        rows = faces.people_index([ed, astrid, {"handle": "h-x"}])
        assert [r["name"] for r in rows] == ["(unknown)", "Astrid Berg", "Ed Grund"]
        assert rows[2] == {"handle": "h-ed", "name": "Ed Grund", "gramps_id": "I0002",
                           "media_count": 2, "rect_count": 1, "immich_ids": ["p1", "p2"]}
        assert rows[0] == {"handle": "h-x", "name": "(unknown)", "gramps_id": "",
                           "media_count": 0, "rect_count": 0, "immich_ids": []}


class TestLinks:
    def test_set_link_adds_the_attribute_once(self):
        gr = FakeGramps(people={"h1": {"handle": "h1"}})
        run(faces.set_link(gr, {}, "h1", "p1"))
        assert faces.person_ids(gr.people["h1"]) == ["p1"]
        assert gr.people["h1"]["attribute_list"][0]["_class"] == "Attribute"
        assert len(gr.updated_people) == 1
        run(faces.set_link(gr, {"p1": "h1"}, "h1", "p1"))
        assert faces.person_ids(gr.people["h1"]) == ["p1"]
        assert len(gr.updated_people) == 1

    def test_a_second_immich_person_joins_the_first(self):
        gr = FakeGramps(people={"h1": linked("h1", "p1")})
        run(faces.set_link(gr, {"p1": "h1"}, "h1", "p2"))
        assert faces.person_ids(gr.people["h1"]) == ["p1", "p2"]

    def test_set_link_moves_a_person_off_another_gramps_person(self):
        gr = FakeGramps(people={"h1": linked("h1", "p1", "p9"), "h2": linked("h2")})
        run(faces.set_link(gr, {"p1": "h1", "p9": "h1"}, "h2", "p1"))
        assert faces.person_ids(gr.people["h1"]) == ["p9"]
        assert faces.person_ids(gr.people["h2"]) == ["p1"]
        assert [p["handle"] for p in gr.updated_people] == ["h1", "h2"]

    def test_a_stale_map_entry_for_a_gone_person_is_harmless(self):
        gr = FakeGramps(people={"h2": linked("h2")})
        run(faces.set_link(gr, {"p1": "h-gone"}, "h2", "p1"))
        assert faces.person_ids(gr.people["h2"]) == ["p1"]

    def test_set_link_on_a_missing_person_raises(self):
        with pytest.raises(GrampsError):
            run(faces.set_link(FakeGramps(), {}, "h-gone", "p1"))

    def test_delete_link_removes_every_immich_person(self):
        person = linked("h1", "p1", "p2")
        person["attribute_list"].append({"type": "Nickname", "value": "Ed"})
        gr = FakeGramps(people={"h1": person})
        assert run(faces.delete_link(gr, "h1")) is True
        assert gr.people["h1"]["attribute_list"] == [{"type": "Nickname", "value": "Ed"}]
        assert len(gr.updated_people) == 1

    def test_delete_link_returns_false_when_nothing_to_remove(self):
        gr = FakeGramps(people={"h1": linked("h1")})
        assert run(faces.delete_link(gr, "h1")) is False
        assert run(faces.delete_link(gr, "h-gone")) is False
        assert gr.updated_people == []


class TestAdoptPersonLinks:
    def _seed(self, conn, *rows):
        with conn:
            conn.executemany(
                "INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at) "
                "VALUES (?, ?, ?, '2026-01-01')", rows)

    def test_moves_rows_onto_the_people_and_drops_the_table(self, conn):
        self._seed(conn, ("h1", "p1", "Ed"), ("h1", "p2", "Ed"), ("h2", "p3", None))
        gr = FakeGramps(people={"h1": linked("h1"), "h2": linked("h2", "p3")})
        assert run(faces.adopt_person_links(conn, gr)) == 2
        assert faces.person_ids(gr.people["h1"]) == ["p1", "p2"]
        assert faces.person_ids(gr.people["h2"]) == ["p3"]
        assert [p["handle"] for p in gr.updated_people] == ["h1", "h1"]
        assert not table_exists(conn, "person_links")

    def test_without_the_table_nothing_is_asked_of_gramps(self, conn):
        with conn:
            conn.execute("DROP TABLE person_links")
        gr = FakeGramps(people={"h1": linked("h1")})
        assert run(faces.adopt_person_links(conn, gr)) == 0
        assert gr.updated_people == []

    def test_a_missing_person_is_skipped(self, conn):
        self._seed(conn, ("h-gone", "p1", "Ghost"), ("h1", "p2", "Ed"))
        gr = FakeGramps(people={"h1": linked("h1")})
        assert run(faces.adopt_person_links(conn, gr)) == 1
        assert faces.person_ids(gr.people["h1"]) == ["p2"]
        assert not table_exists(conn, "person_links")

    def test_a_raising_gramps_leaves_the_table(self, conn):
        class Down(FakeGramps):
            async def get_person(self, handle, ok_404=False):
                raise GrampsError("GET /people → 502")

        self._seed(conn, ("h1", "p1", "Ed"))
        with pytest.raises(GrampsError):
            run(faces.adopt_person_links(conn, Down()))
        assert table_exists(conn, "person_links")
        assert conn.execute("SELECT COUNT(*) FROM person_links").fetchone()[0] == 1


class ResolvingImmich(FakeImmich):
    """Adds the listing and person endpoints resolution needs"""

    def __init__(self, me_id, label, people=None, listed=None, **kw):
        super().__init__(me_id=me_id, **kw)
        self.label = label
        self._people = people or {}
        self._listed = listed if listed is not None else list(self._people)
        self.thumb_requests = []

    async def list_people(self, with_hidden=True):
        return [{"id": pid, "name": self._people[pid], "isHidden": pid.startswith("hidden")}
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


class DownImmich(ResolvingImmich):
    async def get_me(self):
        raise ImmichError(500, "down")

    async def list_people(self, with_hidden=True):
        raise ImmichError(500, "down")


def rows_for(*people):
    return faces.people_index(list(people))


class TestResolution:
    def test_merged_people_carries_account_and_puts_named_people_first(self):
        a = ResolvingImmich("ua", "fh", people={"p1": " Ada Berg ", "hidden-1": ""})
        b = ResolvingImmich("ub", "peter", people={"p2": "Bo Lindqvist "})
        people = run(faces.merged_people([a, b]))
        assert [(p["id"], p["name"], p["account_label"], p["owner_user_id"], p["is_hidden"]) for p in people] == [
            ("p1", "Ada Berg", "fh", "ua", False), ("p2", "Bo Lindqvist", "peter", "ub", False),
            ("hidden-1", "", "fh", "ua", True)]

    def test_merged_people_skips_an_account_that_is_down(self):
        down = DownImmich("ua", "fh", people={"p1": "Astrid"})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed Grund"})
        assert [(p["id"], p["account_label"]) for p in run(faces.merged_people([down, b]))] == [("p2", "peter")]

    def test_resolve_person_probes_accounts_in_order(self):
        a = ResolvingImmich("ua", "fh", people={})
        b = ResolvingImmich("ub", "peter", people={"p2": " Ed "}, listed=[])
        assert run(faces.resolve_person([a, b], "p2")) == {
            "name": "Ed", "owner_user_id": "ub", "account_label": "peter"}
        assert run(faces.resolve_person([a], "p2")) is None

    def test_resolve_person_survives_a_broken_get_me(self):
        class NoMe(ResolvingImmich):
            async def get_me(self):
                raise ImmichError(500, "down")

        info = run(faces.resolve_person([NoMe("ub", "peter", people={"p2": "Ed"})], "p2"))
        assert info == {"name": "Ed", "owner_user_id": "", "account_label": "peter"}

    def test_grouped_links_one_entry_per_linked_gramps_person(self):
        a = ResolvingImmich("ua", "fh", people={"p1": "Ed G", "p3": "Astrid B"})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed Grund "})
        rows = rows_for(named("H1", "Ed", "Grund", "p1", "p2"), named("H2", "Astrid", "Berg", "p3"),
                        named("H3", "Nobody", "Linked"))
        groups = run(faces.grouped_links([a, b], rows))
        assert [g["gramps_handle"] for g in groups] == ["H2", "H1"]
        h1 = groups[1]
        assert h1["links"] == [
            {"gramps_handle": "H1", "immich_person_id": "p1", "person_name": "Ed G",
             "account_label": "fh", "resolved": True},
            {"gramps_handle": "H1", "immich_person_id": "p2", "person_name": "Ed Grund",
             "account_label": "peter", "resolved": True}]

    def test_grouped_links_fall_back_to_a_direct_get_when_the_listing_omits(self):
        b = ResolvingImmich("ub", "peter", people={"p9": "Eleraine"}, listed=[])
        groups = run(faces.grouped_links([b], rows_for(linked("H1", "p9"))))
        assert groups[0]["links"][0]["person_name"] == "Eleraine"
        assert groups[0]["links"][0]["resolved"] is True

    def test_grouped_links_mark_the_unresolvable(self):
        b = ResolvingImmich("ub", "peter", people={})
        groups = run(faces.grouped_links([b], rows_for(linked("H1", "gone"))))
        assert groups[0]["links"] == [{"gramps_handle": "H1", "immich_person_id": "gone", "person_name": "",
                                       "account_label": "", "resolved": False}]

    def test_grouped_links_degrade_when_one_account_is_down(self):
        down = DownImmich("ua", "fh", people={"p1": "Astrid"})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed Grund"})
        groups = run(faces.grouped_links([down, b], rows_for(linked("H1", "p2"))))
        link = groups[0]["links"][0]
        assert (link["person_name"], link["account_label"], link["resolved"]) == ("Ed Grund", "peter", True)

    def test_no_links_no_groups(self):
        assert run(faces.grouped_links([ResolvingImmich("ua", "fh")], rows_for(linked("H1")))) == []

    def test_thumbnail_comes_from_the_first_account_that_serves_it(self):
        a = ResolvingImmich("ua", "fh", people={"p2": "Shadow Ed"})
        b = ResolvingImmich("ub", "peter", people={"p2": "Ed Grund"})
        assert run(faces.person_thumbnail_bytes([a, b], "p2")) == (b"img", "image/jpeg")
        assert (a.thumb_requests, b.thumb_requests) == (["p2"], [])

    def test_thumbnail_falls_back_across_accounts(self):
        a = ResolvingImmich("ua", "fh", people={})
        b = ResolvingImmich("ub", "peter", people={"p9": "Eleraine"})
        content, _mime = run(faces.person_thumbnail_bytes([a, b], "p9"))
        assert content == b"img" and a.thumb_requests == b.thumb_requests == ["p9"]

    def test_thumbnail_mixed_errors_raise_the_hard_error(self):
        class Down(ResolvingImmich):
            async def person_thumbnail(self, person_id):
                raise ImmichError(0, "request failed")

        with pytest.raises(ImmichError) as exc:
            run(faces.person_thumbnail_bytes([ResolvingImmich("ua", "fh"), Down("ub", "peter")], "p9"))
        assert exc.value.status == 0

    def test_thumbnail_nobody_has_is_a_404(self):
        with pytest.raises(ImmichError) as exc:
            run(faces.person_thumbnail_bytes([ResolvingImmich("ua", "fh"), ResolvingImmich("ub", "peter")], "p9"))
        assert exc.value.status == 404
        with pytest.raises(ImmichError) as exc:
            run(faces.person_thumbnail_bytes([], "p9"))
        assert exc.value.status == 404


def apply_links(gramps, immich, conn, apply, selected=None):
    async def collect():
        return [e async for e in faces.apply_links(gramps, [immich], conn, apply=apply, selected=selected)]
    return run(collect())


def items(events):
    return [e for e in events if e.kind == "item"]


def face_of(pid, name):
    return {"person": {"id": pid, "name": name}}


class TestApplyLinks:
    def _world(self, conn):
        mint(conn, "K1", "a1")
        im = FakeImmich(assets={"a1": asset("a1")}, faces={"a1": [face_of("uuid-ed", "Ed")]})
        gr = FakeGramps(media={"K1": {"gramps_id": "K1", "handle": "mh1"}},
                        people={"h-ed": linked("h-ed", "uuid-ed")})
        return im, gr

    def test_preview_writes_nothing(self, conn):
        im, gr = self._world(conn)
        events = apply_links(gr, im, conn, apply=False)
        rows = items(events)
        assert len(rows) == 1
        assert (rows[0].action, rows[0].entity, rows[0].source_id, rows[0].gramps_id) == (
            "would_create", "face", "a1", "K1")
        assert rows[0].title == "img.jpg"
        assert rows[0].data == {"cols": {"Ed": "link"}}
        assert gr.updated_people == [] and gr.people["h-ed"]["media_list"] == []
        assert events[-1].kind == "summary"
        assert events[-1].data == {"faces_linked": 1, "boxes_added": 0, "unreadable": 0, "errors": 0}

    def test_links_are_read_from_gramps_once(self, conn):
        im, gr = self._world(conn)
        apply_links(gr, im, conn, apply=False)
        assert gr.list_people_calls == 1

    def test_row_title_is_the_gramps_media_desc(self, conn):
        im, gr = self._world(conn)
        gr.media["K1"]["desc"] = "Ed at the lake"
        assert items(apply_links(gr, im, conn, apply=False))[0].title == "Ed at the lake"

    def test_progress_events_bracket_the_scan(self, conn):
        im, gr = self._world(conn)
        progress = [e for e in apply_links(gr, im, conn, apply=False) if e.kind == "progress"]
        assert progress and progress[0].data["done"] == 0
        assert progress[-1].data["done"] == progress[-1].data["total"] == 1

    def test_apply_links_the_face_and_a_second_run_is_quiet(self, conn):
        im, gr = self._world(conn)
        events = apply_links(gr, im, conn, apply=True)
        assert [e.action for e in items(events)] == ["created"]
        assert gr.updated_people[0]["media_list"][0]["ref"] == "mh1"
        assert gr.people["h-ed"]["media_list"][0]["ref"] == "mh1"
        gr.updated_people.clear()
        events = apply_links(gr, im, conn, apply=True)
        assert items(events) == [] and gr.updated_people == []
        assert events[-1].data["faces_linked"] == 0

    def test_a_face_box_is_added_to_an_existing_ref(self, conn):
        im, gr = self._world(conn)
        im.faces["a1"] = [{**face_of("uuid-ed", "Ed"), "imageWidth": 100, "imageHeight": 100,
                           "boundingBoxX1": 10, "boundingBoxY1": 10, "boundingBoxX2": 30, "boundingBoxY2": 30}]
        gr.people["h-ed"]["media_list"] = [{"ref": "mh1", "rect": []}]
        events = apply_links(gr, im, conn, apply=True)
        assert [e.action for e in items(events)] == ["updated"]
        assert items(events)[0].data == {"cols": {"Ed": "face box"}}
        assert gr.people["h-ed"]["media_list"][0]["rect"] == [7, 7, 33, 33]
        assert events[-1].data["boxes_added"] == 1

    def test_selected_limits_an_apply(self, conn):
        im, gr = self._world(conn)
        mint(conn, "K2", "a2")
        im.assets["a2"] = asset("a2")
        im.faces["a2"] = [face_of("uuid-ed", "Ed")]
        gr.media["K2"] = {"gramps_id": "K2", "handle": "mh2"}
        events = apply_links(gr, im, conn, apply=True, selected={"face:a2"})
        assert [e.source_id for e in items(events)] == ["a2"]
        assert [p["media_list"][0]["ref"] for p in gr.updated_people] == ["mh2"]
        assert im.faces_requested == ["a2"]

    def test_unknown_people_and_other_persons_do_not_link(self, conn):
        im, gr = self._world(conn)
        im.faces["a1"] = [face_of("uuid-stranger", "Stranger"), {"person": None}]
        events = apply_links(gr, im, conn, apply=True)
        assert items(events) == [] and gr.updated_people == []

    def test_no_links_errors(self, conn):
        im, gr = self._world(conn)
        gr.people["h-ed"] = linked("h-ed")
        events = apply_links(gr, im, conn, apply=True)
        assert events[0].kind == "error" and events[0].detail == "no person links yet"
        assert events[-1].kind == "summary" and len(events) == 2

    def test_withdrawn_and_paperless_rows_are_not_scanned(self, conn):
        im, gr = self._world(conn)
        mint(conn, "K2", "a2")
        mint(conn, "K3", "7", system="paperless")
        with conn:
            conn.execute("UPDATE minted_media SET withdrawn_at='2026-02-01' WHERE gramps_id='K2'")
        events = apply_links(gr, im, conn, apply=False)
        assert events[0].detail == "1 synced media to scan against 1 link(s)"
        assert [e.source_id for e in items(events)] == ["a1"]

    def test_no_rows_ends_after_the_start(self, conn):
        im, gr = self._world(conn)
        events = apply_links(gr, im, conn, apply=True, selected=set())
        assert [e.kind for e in events] == ["started", "summary"]
        assert im.faces_requested == []

    def test_unreadable_asset_counted(self, conn):
        im, gr = self._world(conn)
        mint(conn, "K2", "a2")
        events = apply_links(gr, im, conn, apply=True)
        failed = [e for e in items(events) if e.action == "failed"]
        assert [(e.source_id, e.gramps_id, e.title, e.detail) for e in failed] == [
            ("a2", "K2", "a2", "asset detail unreadable")]
        assert events[-1].data["unreadable"] == 1
        assert events[-1].data["faces_linked"] == 1

    def test_missing_gramps_media_counted(self, conn):
        im, gr = self._world(conn)
        del gr.media["K1"]
        events = apply_links(gr, im, conn, apply=True)
        assert items(events)[0].detail == "no Gramps media with this id"
        assert items(events)[0].title == "img.jpg"
        assert events[-1].data["unreadable"] == 1 and gr.updated_people == []

    def test_a_failing_person_write_is_an_error_row(self, conn):
        class Failing(FakeGramps):
            async def update_person(self, handle, person_obj):
                raise GrampsError("PUT /people → 500")

        im, _ = self._world(conn)
        gr = Failing(media={"K1": {"gramps_id": "K1", "handle": "mh1"}},
                     people={"h-ed": linked("h-ed", "uuid-ed")})
        events = apply_links(gr, im, conn, apply=True)
        failed = items(events)[0]
        assert failed.action == "failed" and failed.detail.startswith("Ed: ")
        assert events[-1].data["errors"] == 1
