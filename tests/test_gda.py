"""Unit tests for the gda.* KV contract (core/gda) and its consumers."""

import pytest

from bifrost.core import db, ids
from bifrost.core.config import SyncImmichConfig
from bifrost.core.gda import dates, scan
from bifrost.modules import sync_immich
from bifrost.web.routes.photos import load_album_ids, save_album_ids, validate_pair


class TestDateValidate:
    def test_year_only(self):
        d = dates.validate({"start": {"year": 1920}})
        assert d["start"] == {"year": 1920, "month": 0, "day": 0}
        assert d["stop"] is None
        assert d["display"] == "1920"
        assert d["sort"] == "1920-07-01"  # midpoint of the (leap) year

    def test_full_date(self):
        d = dates.validate({"start": {"year": 1955, "month": 7, "day": 14}})
        assert d["display"] == "14 July 1955"
        assert d["sort"] == "1955-07-14"

    def test_estimated_about(self):
        d = dates.validate(
            {"modifier": "about", "quality": "estimated", "start": {"year": 1920}}
        )
        assert d["display"] == "estimated about 1920"

    def test_before_sorts_at_lower_bound(self):
        d = dates.validate({"modifier": "before", "start": {"year": 1920}})
        assert d["sort"] == "1920-01-01"

    def test_after_sorts_at_upper_bound(self):
        d = dates.validate({"modifier": "after", "start": {"year": 1920}})
        assert d["sort"] == "1920-12-31"

    def test_range(self):
        d = dates.validate(
            {"modifier": "range", "start": {"year": 1920}, "stop": {"year": 1929}}
        )
        assert d["display"] == "between 1920 and 1929"

    def test_span(self):
        d = dates.validate(
            {"modifier": "span", "start": {"year": 1920}, "stop": {"year": 1929}}
        )
        assert d["display"] == "from 1920 to 1929"

    def test_range_backwards_rejected(self):
        with pytest.raises(dates.DateError):
            dates.validate(
                {"modifier": "range", "start": {"year": 1930}, "stop": {"year": 1920}}
            )

    def test_textonly_needs_text(self):
        with pytest.raises(dates.DateError):
            dates.validate({"modifier": "textonly"})

    def test_textonly(self):
        d = dates.validate({"modifier": "textonly", "text": "wedding day"})
        assert d["display"] == "wedding day"
        assert d["start"] is None and d["sort"] is None

    def test_user_text_wins_display(self):
        d = dates.validate({"start": {"year": 1920}, "text": "circa 1920s"})
        assert d["display"] == "circa 1920s"

    def test_day_needs_month(self):
        with pytest.raises(dates.DateError):
            dates.validate({"start": {"year": 1920, "month": 0, "day": 5}})

    def test_day_bounded_by_month(self):
        with pytest.raises(dates.DateError):
            dates.validate({"start": {"year": 1920, "month": 2, "day": 30}})

    def test_leap_day_ok(self):
        d = dates.validate({"start": {"year": 1920, "month": 2, "day": 29}})
        assert d["sort"] == "1920-02-29"

    def test_year_required(self):
        with pytest.raises(dates.DateError):
            dates.validate({"start": {"month": 3}})
        with pytest.raises(dates.DateError):
            dates.validate({})

    def test_unknown_modifier_and_quality(self):
        with pytest.raises(dates.DateError):
            dates.validate({"modifier": "sometime", "start": {"year": 1920}})
        with pytest.raises(dates.DateError):
            dates.validate({"quality": "guessed", "start": {"year": 1920}})

    def test_bool_and_fractional_rejected(self):
        with pytest.raises(dates.DateError):
            dates.validate({"start": {"year": True}})
        with pytest.raises(dates.DateError):
            dates.validate({"start": {"year": 1920.5}})

    def test_output_feeds_gramps_mapping(self):
        # The whole point of the shared shape: validate() output must be
        # consumable by the sync's Gramps translation without massaging.
        for payload in (
            {"start": {"year": 1920}},
            {"modifier": "about", "quality": "estimated", "start": {"year": 1920}},
            {"modifier": "range", "start": {"year": 1920}, "stop": {"year": 1929, "month": 12}},
            {"modifier": "textonly", "text": "wedding day"},
        ):
            gramps = sync_immich.gda_date_to_gramps(dates.validate(payload))
            assert gramps["_class"] == "Date"


class TestContractPins:
    def test_sync_modifier_codes_match_tuple_order(self):
        # gda.dates tuple order IS the Gramps integer code; sync_immich keeps
        # an explicit map. If either side changes alone, this fails.
        assert sync_immich._MODIFIERS == {m: i for i, m in enumerate(dates.MODIFIERS)}

    def test_sync_quality_codes_match_tuple_order(self):
        assert sync_immich._QUALITIES == {q: i for i, q in enumerate(dates.QUALITIES)}

    def test_scan_alphabet_is_the_id_alphabet(self):
        # Scan base ids ARE Gramps media ids — one safe alphabet (core.ids).
        assert ids.MANUAL_ID_RE.pattern == scan._BASE_RE.pattern


class TestScanValidate:
    def test_bare(self):
        s = scan.validate({"base": "vgrn54"})
        assert s["base"] == "VGRN54"
        assert s["label"] == "VGRN54"
        assert s["ordinal"] is None

    def test_original(self):
        assert scan.validate({"base": "VGRN54", "role": "o"})["label"] == "VGRN54_o"

    def test_ordinal_roles(self):
        s = scan.validate({"base": "VGRN54", "role": "v", "ordinal": 1})
        assert s["label"] == "VGRN54_v01"
        with pytest.raises(scan.ScanError):
            scan.validate({"base": "VGRN54", "role": "v"})
        with pytest.raises(scan.ScanError):
            scan.validate({"base": "VGRN54", "role": "c", "ordinal": 100})

    def test_unsafe_alphabet_rejected(self):
        for bad in ("VGRN50", "VGRN5I", "VGRN5L", "VGRN5O", "VGRN51", "VGRN5"):
            with pytest.raises(scan.ScanError):
                scan.validate({"base": bad})

    def test_scan_no(self):
        s = scan.validate({"base": "VGRN54", "scan_no": "A000277"})
        assert s["scan_no"] == "a000277"
        with pytest.raises(scan.ScanError):
            scan.validate({"base": "VGRN54", "scan_no": "277"})

    def test_unknown_role(self):
        with pytest.raises(scan.ScanError):
            scan.validate({"base": "VGRN54", "role": "x"})


class TestSyncScanHelpers:
    CFG = SyncImmichConfig()

    def test_dates_equal_ignores_api_decoration(self):
        # Stored Gramps dates come back with sortval/calendar/etc. — only the
        # fields bifrost writes may decide equality.
        stored = {"_class": "Date", "dateval": [0, 0, 1920, False], "modifier": 3,
                  "quality": 1, "text": "", "sortval": 2422325, "calendar": 0}
        fresh = sync_immich.gda_date_to_gramps(
            {"modifier": "about", "quality": "estimated", "start": {"year": 1920}})
        assert sync_immich.dates_equal(stored, fresh)

    def test_dates_differ(self):
        assert not sync_immich.dates_equal(
            {"dateval": [0, 0, 1920, False], "modifier": 3, "quality": 1},
            {"dateval": [0, 0, 1921, False], "modifier": 3, "quality": 1})
        assert not sync_immich.dates_equal(None, {"dateval": [0, 0, 1920, False]})

    def test_update_plan_title_and_date(self):
        kv = {"gda.gramps": {"title": "Grandma, 1920"},
              "gda.date": {"modifier": "about", "quality": "regular",
                           "start": {"year": 1920, "month": 0, "day": 0},
                           "display": "about 1920"}}
        media = {"desc": "img_0001.jpg", "date": None}
        cols = sync_immich.update_plan(kv, {"originalFileName": "img_0001.jpg"}, media, self.CFG)
        assert set(cols) == {"title", "date"}

    def test_update_plan_in_sync(self):
        kv = {"gda.gramps": {"title": "Grandma, 1920"},
              "gda.date": {"modifier": "about", "quality": "regular",
                           "start": {"year": 1920, "month": 0, "day": 0}}}
        media = {"desc": "Grandma, 1920",
                 "date": {"dateval": [0, 0, 1920, False], "modifier": 3,
                          "quality": 0, "text": ""}}
        assert sync_immich.update_plan(kv, {}, media, self.CFG) == {}

    def test_update_plan_never_clears_gramps_date(self):
        # Gramps has a date, the asset has no gda.date → hands off.
        media = {"desc": "t", "date": {"dateval": [1, 1, 1920, False],
                                       "modifier": 0, "quality": 0, "text": ""}}
        assert sync_immich.update_plan({"gda.gramps": {"title": "t"}}, {}, media, self.CFG) == {}

    def test_verso_detection(self):
        assert sync_immich.is_verso({"gda.verso": {"recto": "some-id"}}, self.CFG)
        assert not sync_immich.is_verso({"gda.verso": {"verso": "some-id"}}, self.CFG)
        assert not sync_immich.is_verso({}, self.CFG)

    MAPPED = SyncImmichConfig(path_mappings=(("/usr/src/app/upload/upload/", "immich/"),))

    def test_update_plan_repoints_changed_file(self):
        # The stack's main changed → the media must follow the new main's file.
        kv = {"gda.gramps": {"title": "t"}}
        asset = {"originalPath": "/usr/src/app/upload/upload/u1/new.jpg"}
        media = {"desc": "t", "path": "immich/u1/old.jpg"}
        cols = sync_immich.update_plan(kv, asset, media, self.MAPPED)
        assert set(cols) == {"file"}
        assert "immich/u1/new.jpg" in cols["file"]

    def test_update_plan_same_file_no_repoint(self):
        kv = {"gda.gramps": {"title": "t"}}
        asset = {"originalPath": "/usr/src/app/upload/upload/u1/a.jpg"}
        media = {"desc": "t", "path": "immich/u1/a.jpg"}
        assert sync_immich.update_plan(kv, asset, media, self.MAPPED) == {}

    def test_update_plan_unmapped_path_hard_fails(self):
        with pytest.raises(sync_immich.SyncError):
            sync_immich.update_plan(
                {"gda.gramps": {"title": "t"}},
                {"originalPath": "/somewhere/else/a.jpg"},
                {"desc": "t", "path": "immich/u1/a.jpg"},
                self.MAPPED,
            )


class TestPlanPrimaryMove:
    CFG = SyncImmichConfig()

    def test_moves_photo_keys_not_scan(self):
        from bifrost.web.routes.photos import plan_primary_move
        old_kv = {
            "gda.date": {"modifier": "about"},
            "gda.gramps": {"gramps_id": "ABCDEF"},
            "gda.verso": {"verso": "v-id"},
            "gda.scan": {"role": "o"},  # per-FILE — must stay behind
        }
        writes, deletes = plan_primary_move(old_kv, self.CFG)
        assert set(writes) == {"gda.date", "gda.gramps", "gda.verso"}
        assert set(deletes) == {"gda.date", "gda.gramps", "gda.verso"}
        assert "gda.scan" not in writes

    def test_nothing_to_move(self):
        from bifrost.web.routes.photos import plan_primary_move
        assert plan_primary_move({"gda.scan": {"role": "o"}}, self.CFG) == ({}, [])


def test_sync_counts_are_all_initialized():
    """Every counts["..."] increment in sync_assets must exist in the counts
    literal — a missing key is a KeyError that aborts an apply mid-batch
    (versions_updated was once missing; this pins the whole class)."""
    import inspect
    import re

    src = inspect.getsource(sync_immich.sync_assets)
    init = re.search(r"counts\s*=\s*\{(.*?)\}", src, re.S).group(1)
    declared = set(re.findall(r"\"(\w+)\"\s*:", init))
    used = set(re.findall(r"counts\[\"(\w+)\"\]", src))
    assert used <= declared, f"uninitialized counts keys: {used - declared}"


class TestValidatePair:
    CFG = SyncImmichConfig()

    def test_clean_pair_ok(self):
        assert validate_pair({}, {"gda.date": {"modifier": "regular"}}, self.CFG) is None

    def test_already_paired_rejected(self):
        assert validate_pair({"gda.verso": {"verso": "x"}}, {}, self.CFG)
        assert validate_pair({}, {"gda.verso": {"recto": "x"}}, self.CFG)

    def test_synced_verso_rejected(self):
        # A synced asset owns a Gramps media object — hiding it behind a
        # recto would orphan that object from all future updates.
        assert validate_pair({}, {"gda.gramps": {"gramps_id": "ABCDEF"}}, self.CFG)


class TestPlanStack:
    CFG = SyncImmichConfig()

    def _stack_of(self):
        return {"m1": {"id": "S1", "primaryAssetId": "p1"},
                "p1": {"id": "S1", "primaryAssetId": "p1"}}

    def test_new_stack_first_selected_is_primary(self):
        from bifrost.web.routes.photos import plan_stack
        ordered, primary = plan_stack(["a", "b", "c"], {}, {}, self.CFG)
        assert primary == "a"
        assert ordered == ["a", "b", "c"]

    def test_merge_keeps_existing_primary(self):
        from bifrost.web.routes.photos import plan_stack
        ordered, primary = plan_stack(["x", "m1"], self._stack_of(), {}, self.CFG)
        assert primary == "p1"
        assert ordered[0] == "p1" and set(ordered) == {"p1", "x", "m1"}

    def test_two_stacks_rejected(self):
        from bifrost.web.routes.photos import plan_stack
        stack_of = {**self._stack_of(), "m2": {"id": "S2", "primaryAssetId": "m2"}}
        with pytest.raises(ValueError):
            plan_stack(["m1", "m2"], stack_of, {}, self.CFG)

    def test_verso_joiner_rejected(self):
        from bifrost.web.routes.photos import plan_stack
        kv = {"b": {"gda.verso": {"recto": "elsewhere"}}}
        with pytest.raises(ValueError):
            plan_stack(["a", "b"], {}, kv, self.CFG)

    def test_synced_joiner_rejected(self):
        from bifrost.web.routes.photos import plan_stack
        kv = {"b": {"gda.gramps": {"gramps_id": "ABCDEF"}}}
        with pytest.raises(ValueError):
            plan_stack(["a", "b"], {}, kv, self.CFG)

    def test_synced_primary_allowed(self):
        # The first-selected (future main) may be synced — it stays visible.
        from bifrost.web.routes.photos import plan_stack
        kv = {"a": {"gda.gramps": {"gramps_id": "ABCDEF"}}}
        _, primary = plan_stack(["a", "b"], {}, kv, self.CFG)
        assert primary == "a"


class TestSyncEnabledKnob:
    """sync.immich.enabled replaces urd's empty-bifrost.base_url dev-safety
    knob — absent must mean enabled, explicit false must stick."""

    def _cfg(self, tmp_path, immich_block):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "gramps: {base_url: x, username: u, password: p}\n"
            "paperless: {base_url: x, api_token: t}\n"
            f"sync:\n  immich:\n    {immich_block}\n"
        )
        from bifrost.core.config import load_config
        return load_config(cfg)

    def test_absent_means_enabled(self, tmp_path):
        assert self._cfg(tmp_path, "public_url: x").sync_immich.enabled is True

    def test_explicit_false(self, tmp_path):
        assert self._cfg(tmp_path, "enabled: false").sync_immich.enabled is False


class TestAlbumSettings:
    def test_roundtrip(self, tmp_path):
        conn = db.connect(tmp_path / "t.db")
        assert load_album_ids(conn) == []
        save_album_ids(conn, ["a", "b"])
        assert load_album_ids(conn) == ["a", "b"]
        save_album_ids(conn, ["c"])  # overwrite, not append
        assert load_album_ids(conn) == ["c"]
        conn.close()

    def test_corrupt_value_is_empty(self, tmp_path):
        conn = db.connect(tmp_path / "t.db")
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES ('photos.album_ids', 'not json')"
        )
        assert load_album_ids(conn) == []
        conn.close()
