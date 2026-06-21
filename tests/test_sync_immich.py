"""Unit tests for the pure sync logic ported from immich_to_gramps.py."""

import asyncio

from bifrost.core import db
from bifrost.core.config import SyncImmichConfig
from bifrost.modules import sync_immich
from bifrost.modules.sync_immich import (
    build_gramps_date,
    find_closest_place,
    format_gramps_date,
    parse_gramps_coord,
    translate_path,
)

MAPPINGS = (
    {"immich_prefix": "/usr/src/app/upload/upload/", "gramps_prefix": "immich/"},
    {"immich_prefix": "/mnt/archive/", "gramps_prefix": "archive/"},
)


def test_translate_path_mappings():
    assert translate_path("/usr/src/app/upload/upload/2026/04/p.jpg", MAPPINGS) \
        == "immich/2026/04/p.jpg"
    assert translate_path("/mnt/archive/box1/scan.tif", MAPPINGS) == "archive/box1/scan.tif"


def test_translate_path_fallback_filename_only():
    assert translate_path("/somewhere/else/photo.jpg", MAPPINGS) == "immich/photo.jpg"


def _asset(tags=(), dt="1955-06-17T10:00:00Z"):
    return {
        "exifInfo": {"dateTimeOriginal": dt},
        "tags": [{"value": t} for t in tags],
    }


def test_date_plain():
    d = build_gramps_date(_asset())
    assert d["dateval"] == [17, 6, 1955, False]
    assert d["modifier"] == 0 and d["quality"] == 0
    assert format_gramps_date(d) == "1955-06-17"


def test_date_approximate_strips_day():
    d = build_gramps_date(_asset(tags=["Date/Approximate"]))
    assert d["dateval"] == [0, 6, 1955, False]
    assert d["modifier"] == 3  # ABOUT
    assert format_gramps_date(d) == "About 1955-06"


def test_date_qualifier_groups_stack():
    d = build_gramps_date(_asset(tags=["Date/Before", "Date/Estimated", "Date/Year"]))
    assert d["dateval"] == [0, 0, 1955, False]
    assert d["modifier"] == 1 and d["quality"] == 1
    assert format_gramps_date(d) == "Est. Before 1955"


def test_date_month_precision():
    d = build_gramps_date(_asset(tags=["Date/Month", "Date/Calculated"]))
    assert d["dateval"] == [0, 6, 1955, False]
    assert d["quality"] == 2
    assert format_gramps_date(d) == "Calc. 1955-06"


def test_date_missing():
    assert build_gramps_date({"exifInfo": {}, "tags": []}) is None


def test_parse_gramps_coord():
    assert parse_gramps_coord("45.5") == 45.5
    assert parse_gramps_coord("N45.5") == 45.5
    assert parse_gramps_coord("W92.9") == -92.9
    assert parse_gramps_coord("S10") == -10.0
    assert parse_gramps_coord("") is None
    assert parse_gramps_coord("garbage") is None


def test_find_closest_place_within_250m():
    near = {"lat": "45.0001", "long": "-92.0001", "name": {"value": "Near"}}
    far = {"lat": "45.1", "long": "-92.1", "name": {"value": "Far"}}
    result = find_closest_place(45.0, -92.0, [far, near])
    assert result is not None
    place, dist = result
    assert place["name"]["value"] == "Near"
    assert dist < 0.25


def test_find_closest_place_none_beyond_250m():
    far = {"lat": "45.1", "long": "-92.1", "name": {"value": "Far"}}
    assert find_closest_place(45.0, -92.0, [far]) is None


# ---------------------------------------------------------------------------
# Version phase (Immich stacks → displayed version). Driven through the real
# `sync(..., versions_only=True)` generator with stub clients (no live calls).
# Detection (phase 2), repoint/persist/face-clear (phase 3), tag propagation +
# members population (phase 4).
# ---------------------------------------------------------------------------

CFG = SyncImmichConfig()  # no path_mappings, no place linking
CFG_MAP = SyncImmichConfig(
    sync_tags=("Sync/Gramps",), public_url="https://img.example",
    path_mappings=({"immich_prefix": "/usr/src/app/upload/upload/",
                    "gramps_prefix": "immich/"},))


class _FakeImmich:
    def __init__(self, assets, extra=None, stacks=None, faces=None, existing_tags=None):
        self._tagged = [a["id"] for a in assets]            # the sync-tagged universe
        self._by_id = {a["id"]: a for a in assets}
        for a in (extra or []):                              # gettable but not tagged
            self._by_id[a["id"]] = a
        self._stacks = stacks or {}                          # {stack_id: {primaryAssetId, assets}}
        self._faces = faces or {}                            # {asset_id: [face, ...]}
        # tags that "exist" (resolve_tag_id returns None otherwise) — sync tag
        # always exists; upserts add; opt-in tags can be pre-seeded.
        self._existing_tags = {"Sync/Gramps", *(existing_tags or [])}
        self.tag_calls = []                                  # recorded (tag_id, [asset_ids])
        self.untag_calls = []                                # recorded (tag_id, [asset_ids])
        self.upserts = []                                    # recorded tag values
        self.created_stacks = []                             # recorded [asset_ids]

    async def resolve_tag_id(self, value):
        return ("tag:" + value) if value in self._existing_tags else None

    async def search_assets_by_tag(self, tid):
        return [{"id": i} for i in self._tagged]

    async def get_asset(self, aid):
        return self._by_id[aid]   # KeyError == "deleted/unavailable" path

    async def get_stack(self, sid):
        s = self._stacks[sid]
        return {"id": sid, "primaryAssetId": s["primaryAssetId"], "assets": s["assets"]}

    async def get_faces(self, aid):
        return self._faces.get(aid, [])

    async def upsert_tags(self, values):
        self.upserts += list(values)
        self._existing_tags.update(values)
        return [{"id": "tag:" + v, "value": v} for v in values]

    async def tag_assets(self, tid, ids):
        self.tag_calls.append((tid, list(ids)))
        return []

    async def untag_assets(self, tid, ids):
        self.untag_calls.append((tid, list(ids)))
        return []

    async def create_stack(self, asset_ids):
        sid = "SNEW"
        self.created_stacks.append(list(asset_ids))
        self._stacks[sid] = {"primaryAssetId": asset_ids[0],
                             "assets": [{"id": i, "checksum": "ck-" + i} for i in asset_ids]}
        # the assets are now stackable members
        return {"id": sid, "primaryAssetId": asset_ids[0],
                "assets": self._stacks[sid]["assets"]}


class _FakeGramps:
    def __init__(self, media, backlinks=None, objects=None):
        self._media = media
        self._by_gid = {m["gramps_id"]: m for m in media}
        self._backlinks = backlinks or {}     # {media_handle: {type: [obj_handle]}}
        self._objects = objects or {}          # {(api_path, handle): obj} (incl. persons)
        self.updated_media = []                # recorded (handle, obj)
        self.updated_objects = []              # recorded (api_path, handle, obj)
        self.updated_persons = []              # recorded (handle, obj)

    async def list_media(self):
        return self._media

    async def list_media_gramps_ids(self):
        return {m["gramps_id"] for m in self._media if m.get("gramps_id")}

    async def get_media_by_gramps_id(self, gid):
        return self._by_gid.get(gid)

    async def get_media_backlinks(self, handle):
        return self._backlinks.get(handle, {})

    async def get_object(self, api_path, handle, **kw):
        return self._objects[(api_path, handle)]

    async def update_media(self, handle, obj):
        self.updated_media.append((handle, obj))

    async def update_object(self, api_path, handle, obj):
        self._objects[(api_path, handle)] = obj
        self.updated_objects.append((api_path, handle, obj))

    # apply_face goes through the person endpoints — share the ("people", h) store
    # so the clear step and re-derivation see the same object.
    async def get_person(self, handle):
        return self._objects[("people", handle)]

    async def update_person(self, handle, obj):
        self._objects[("people", handle)] = obj
        self.updated_persons.append((handle, obj))


def _media(asset_id, gid, path="old/p.jpg", mime="image/jpeg", desc=""):
    return {"_class": "Media", "gramps_id": gid, "handle": "H" + gid, "desc": desc,
            "path": path, "mime": mime,
            "attribute_list": [
                {"type": "Immich ID", "value": asset_id},
                {"type": "Immich URL", "value": "http://x/photos/" + asset_id}]}


def _stack(stack_id, primary, count=2):
    return {"id": stack_id, "primaryAssetId": primary, "assetCount": count}


def _vasset(asset_id, stack=None, base_tag=None, **extra):
    a = {"id": asset_id, "tags": [{"value": base_tag}] if base_tag else []}
    if stack is not None:
        a["stack"] = stack
    a.update(extra)
    return a


def _run(conn, assets, media=None, *, apply=False, extra=None, gramps=None,
         stacks=None, faces=None, existing_tags=None, versions_only=True, cfg=CFG):
    g = gramps if gramps is not None else _FakeGramps(media or [])
    im = _FakeImmich(assets, extra=extra, stacks=stacks, faces=faces,
                     existing_tags=existing_tags)

    async def go():
        out = {"summary": None, "would": [], "updated": [], "failed": [], "created": []}
        async for ev in sync_immich.sync(g, im, conn, cfg, apply=apply,
                                         versions_only=versions_only):
            if ev.kind == "summary":
                out["summary"] = ev.data
            elif ev.action == "would_update":
                out["would"].append(ev)
            elif ev.action == "updated":
                out["updated"].append(ev)
            elif ev.action == "failed":
                out["failed"].append(ev)
            elif ev.action in ("created", "would_create"):
                out["created"].append(ev)
        return out, g, im
    return asyncio.run(go())


def _attr(media_obj, attr_type):
    return next(a["value"] for a in media_obj["attribute_list"] if a["type"] == attr_type)


def _row(conn, gid):
    return conn.execute("SELECT * FROM immich_versions WHERE gramps_id=?", (gid,)).fetchone()


def _members(conn, gid):
    return conn.execute(
        "SELECT asset_id, checksum, seq FROM immich_version_members"
        " WHERE gramps_id=? ORDER BY seq", (gid,)).fetchall()


def _tagged_assets(im, tag_value):
    """All asset ids that got tagged with the tag of this full-path value."""
    out = set()
    for tid, ids in im.tag_calls:
        if tid == "tag:" + tag_value:
            out.update(ids)
    return out


# ---- detection (phase 2) --------------------------------------------------

def test_version_unmanaged_stack_ignored(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    out, _, _ = _run(conn, [_vasset("A1", stack=_stack("S1", "A1"))], [_media("A1", "AAAAAA")])
    s = out["summary"]
    assert s["stacks_seen"] == 1 and s["stacks_managed"] == 0
    assert s["baselined"] == 0 and s["versions_updated"] == 0
    assert out["would"] == [] and out["updated"] == []


def test_version_divergence_preview_writes_nothing(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    gramps = _FakeGramps([_media("A1", "AAAAAA")])
    a2 = _vasset("A2", stack=_stack("S1", "A2"),
                 originalPath="/usr/src/app/upload/upload/2026/v2.jpg",
                 originalMimeType="image/png", checksum="ck2", type="IMAGE")
    out, g, im = _run(conn,
                      [_vasset("A1", stack=_stack("S1", "A2"), base_tag="Gramps/Base/AAAAAA")],
                      apply=False, extra=[a2], gramps=gramps, cfg=CFG_MAP)
    assert out["summary"]["versions_updated"] == 1
    assert len(out["would"]) == 1 and out["updated"] == []
    assert g.updated_media == [] and im.tag_calls == []
    assert _row(conn, "AAAAAA") is None


def test_version_managed_via_optin_tag_on_other_member(tmp_path):
    # Peter's real case: the Gramps/Base/<id> tag sits on the NON-displayed
    # member, not the synced asset. Detection must still treat the stack as
    # managed (the tag exists), so a divergence repoints.
    conn = db.connect(tmp_path / "t.db")
    gramps = _FakeGramps([_media("A1", "AAAAAA")])
    a2 = _vasset("A2", stack=_stack("S1", "A2"),
                 originalPath="/usr/src/app/upload/upload/2026/v2.jpg",
                 originalMimeType="image/png", checksum="ck2", type="IMAGE")
    stacks = {"S1": {"primaryAssetId": "A2",
                     "assets": [{"id": "A1", "checksum": "ck1"}, {"id": "A2", "checksum": "ck2"}]}}
    out, g, _ = _run(conn,
                     [_vasset("A1", stack=_stack("S1", "A2"))],  # NO base tag on A1
                     apply=False, extra=[a2], gramps=gramps, stacks=stacks,
                     existing_tags=["Gramps/Base/AAAAAA"], cfg=CFG_MAP)
    assert out["summary"]["stacks_managed"] == 1
    assert out["summary"]["versions_updated"] == 1
    assert len(out["would"]) == 1


def test_version_non_stacked_synced_photo_ignored(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    out, _, _ = _run(conn, [_vasset("A1", base_tag="Gramps/Base/AAAAAA")], [_media("A1", "AAAAAA")])
    assert out["summary"]["stacks_seen"] == 0 and out["summary"]["stacks_managed"] == 0
    assert out["would"] == []


# ---- baseline + repoint + persistence + propagation (phases 3-4) ----------

def test_version_managed_baseline_persists_and_propagates(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    stacks = {"S1": {"primaryAssetId": "A1",
                     "assets": [{"id": "A1", "checksum": "ck1"}, {"id": "AB", "checksum": "ckb"}]}}
    out, _, im = _run(conn,
                      [_vasset("A1", stack=_stack("S1", "A1"), base_tag="Gramps/Base/AAAAAA",
                               checksum="ck1")],
                      [_media("A1", "AAAAAA")], apply=True, stacks=stacks, cfg=CFG_MAP)
    assert out["summary"]["baselined"] == 1 and out["summary"]["versions_updated"] == 0
    # row + members persisted
    r = _row(conn, "AAAAAA")
    assert r["current_asset_id"] == "A1" and r["member_count"] == 2 and r["stack_id"] == "S1"
    assert [m["asset_id"] for m in _members(conn, "AAAAAA")] == ["A1", "AB"]
    # both the sync tag and the base tag propagated onto EVERY member
    assert _tagged_assets(im, "Sync/Gramps") == {"A1", "AB"}
    assert _tagged_assets(im, "Gramps/Base/AAAAAA") == {"A1", "AB"}


def test_version_divergence_apply_repoints_and_tags_new_primary(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    media = _media("A1", "AAAAAA")
    gramps = _FakeGramps(
        [media],
        backlinks={"HAAAAAA": {"person": ["P1"]}},
        objects={("people", "P1"): {"handle": "P1",
                 "media_list": [{"ref": "HAAAAAA", "rect": [1, 2, 3, 4]}]}})
    a2 = _vasset("A2", stack=_stack("S1", "A2"),
                 originalPath="/usr/src/app/upload/upload/2026/v2.jpg",
                 originalMimeType="image/png", checksum="ck2", type="IMAGE")
    stacks = {"S1": {"primaryAssetId": "A2",
                     "assets": [{"id": "A1", "checksum": "ck1"}, {"id": "A2", "checksum": "ck2"}]}}
    out, g, im = _run(conn,
                      [_vasset("A1", stack=_stack("S1", "A2"), base_tag="Gramps/Base/AAAAAA")],
                      apply=True, extra=[a2], gramps=gramps, stacks=stacks, cfg=CFG_MAP)
    s = out["summary"]
    assert s["versions_updated"] == 1 and s["faces_cleared"] == 1

    # repointed in place — base id + handle FROZEN, only path/mime/attrs change
    handle, obj = g.updated_media[0]
    assert handle == "HAAAAAA" and obj["gramps_id"] == "AAAAAA"
    assert _attr(obj, "Immich ID") == "A2"
    assert _attr(obj, "Immich URL") == "https://img.example/photos/A2"
    assert obj["path"] == "immich/2026/v2.jpg" and obj["mime"] == "image/png"
    # face rect cleared
    assert g.updated_objects[0][2]["media_list"][0]["rect"] is None
    # row repointed to A2; the NEW primary is now tagged into the sync universe
    assert _row(conn, "AAAAAA")["current_asset_id"] == "A2"
    assert "A2" in _tagged_assets(im, "Sync/Gramps")
    assert _tagged_assets(im, "Gramps/Base/AAAAAA") == {"A1", "A2"}


def test_version_repoint_rederives_linked_face(tmp_path):
    # A linked person whose face Immich still detects on the new primary gets
    # its rect re-drawn (cleared → re-derived → 0 pending).
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO person_links (gramps_handle, immich_person_id, label,"
                 " created_at) VALUES (?,?,?,?)", ("PH1", "IP1", None, "2026-06-21T00:00:00"))
    conn.commit()
    person = {"handle": "PH1", "media_list": [{"ref": "HAAAAAA", "rect": [1, 2, 3, 4]}]}
    gramps = _FakeGramps(
        [_media("A1", "AAAAAA")],
        backlinks={"HAAAAAA": {"person": ["PH1"]}},
        objects={("people", "PH1"): person})
    a2 = _vasset("A2", stack=_stack("S1", "A2"),
                 originalPath="/usr/src/app/upload/upload/2026/v2.jpg",
                 originalMimeType="image/png", checksum="ck2", type="IMAGE")
    stacks = {"S1": {"primaryAssetId": "A2",
                     "assets": [{"id": "A1", "checksum": "ck1"}, {"id": "A2", "checksum": "ck2"}]}}
    faces = {"A2": [{"person": {"id": "IP1", "name": "Grandma"},
                     "imageWidth": 1000, "imageHeight": 1000,
                     "boundingBoxX1": 100, "boundingBoxY1": 100,
                     "boundingBoxX2": 300, "boundingBoxY2": 300}]}
    out, g, _ = _run(conn,
                     [_vasset("A1", stack=_stack("S1", "A2"), base_tag="Gramps/Base/AAAAAA")],
                     apply=True, extra=[a2], gramps=gramps, stacks=stacks, faces=faces, cfg=CFG_MAP)
    assert out["summary"]["faces_cleared"] == 1
    assert out["summary"]["faces_rederived"] == 1
    # the person's rect was cleared then re-drawn to the new box (pad 0.15)
    assert person["media_list"][0]["rect"] == [7, 7, 33, 33]
    assert "1 cleared / 1 re-derived / 0 pending" in out["updated"][0].data["cols"]["faces"]


def test_version_member_added_repropagates(tmp_path):
    # Managed + in sync, but a 3rd version was added → re-tag + refresh members.
    conn = db.connect(tmp_path / "t.db")
    sync_immich._set_iversion(conn, "AAAAAA", "S1", "A1", "ck1", 2)  # stored count 2
    stacks = {"S1": {"primaryAssetId": "A1", "assets": [
        {"id": "A1", "checksum": "ck1"}, {"id": "AB", "checksum": "ckb"},
        {"id": "AC", "checksum": "ckc"}]}}
    out, _, im = _run(conn,
                      [_vasset("A1", stack=_stack("S1", "A1", count=3), checksum="ck1")],
                      [_media("A1", "AAAAAA")], apply=True, stacks=stacks, cfg=CFG_MAP)
    assert out["summary"]["baselined"] == 0  # not first sight
    r = _row(conn, "AAAAAA")
    assert r["member_count"] == 3
    assert [m["asset_id"] for m in _members(conn, "AAAAAA")] == ["A1", "AB", "AC"]
    assert _tagged_assets(im, "Sync/Gramps") == {"A1", "AB", "AC"}


def test_version_repoint_unmapped_path_fails(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    gramps = _FakeGramps([_media("A1", "AAAAAA")])
    a2 = _vasset("A2", stack=_stack("S1", "A2"), originalPath="/nope/v2.jpg",
                 originalMimeType="image/png", checksum="ck2", type="IMAGE")
    out, g, im = _run(conn,
                      [_vasset("A1", stack=_stack("S1", "A2"), base_tag="Gramps/Base/AAAAAA")],
                      apply=True, extra=[a2], gramps=gramps, cfg=CFG_MAP)
    assert out["summary"]["versions_updated"] == 0 and out["summary"]["errors"] == 1
    assert len(out["failed"]) == 1 and g.updated_media == [] and im.tag_calls == []
    assert _row(conn, "AAAAAA") is None


def test_version_repoint_deleted_primary_fails(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    gramps = _FakeGramps([_media("A1", "AAAAAA")])
    out, g, im = _run(conn,  # A2 not provided → get_asset raises
                      [_vasset("A1", stack=_stack("S1", "A2"), base_tag="Gramps/Base/AAAAAA")],
                      apply=True, gramps=gramps, cfg=CFG_MAP)
    assert out["summary"]["versions_updated"] == 0 and out["summary"]["errors"] == 1
    assert len(out["failed"]) == 1 and g.updated_media == []


def test_version_managed_via_db_row_without_tag(tmp_path):
    # No Gramps/Base tag, but an immich_versions row exists → still managed.
    conn = db.connect(tmp_path / "t.db")
    sync_immich._set_iversion(conn, "AAAAAA", "S1", "A1", "ck", 2)
    gramps = _FakeGramps([_media("A1", "AAAAAA")])
    a2 = _vasset("A2", stack=_stack("S1", "A2"),
                 originalPath="/usr/src/app/upload/upload/2026/v2.jpg",
                 originalMimeType="image/png", checksum="ck2", type="IMAGE")
    out, _, _ = _run(conn, [_vasset("A1", stack=_stack("S1", "A2"))],
                     apply=False, extra=[a2], gramps=gramps, cfg=CFG_MAP)
    assert out["summary"]["stacks_managed"] == 1
    assert out["summary"]["versions_updated"] == 1


# ---- interactive version API (phase 6a) -----------------------------------

def test_version_set_reads_live_stack_and_cache(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    sync_immich._set_iversion(conn, "AAAAAA", "S1", "A1", "ck1", 2)  # managed
    conn.execute("INSERT INTO immich_version_members (gramps_id, asset_id, checksum,"
                 " role, label, seq) VALUES ('AAAAAA','A2','ck2','ai','restored 2026',2)")
    conn.commit()
    im = _FakeImmich(
        [_vasset("A1", stack=_stack("S1", "A1"))],
        extra=[_vasset("A2")],
        stacks={"S1": {"primaryAssetId": "A1",
                       "assets": [{"id": "A1", "checksum": "ck1", "originalFileName": "p.jpg"},
                                  {"id": "A2", "checksum": "ck2", "originalFileName": "p2.jpg"}]}})
    g = _FakeGramps([_media("A1", "AAAAAA")])
    out = asyncio.run(sync_immich.version_set(im, g, conn, CFG_MAP, "A1"))
    assert out["versioned"] and out["managed"]
    assert out["gramps_id"] == "AAAAAA" and out["primary_asset_id"] == "A1"
    a1, a2 = out["members"]
    assert a1["asset_id"] == "A1" and a1["is_displayed"] is True
    assert a2["asset_id"] == "A2" and a2["is_displayed"] is False
    assert a2["role"] == "ai" and a2["label"] == "restored 2026"


def test_version_set_unstacked_returns_not_versioned(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    im = _FakeImmich([_vasset("A1")])  # no stack
    g = _FakeGramps([_media("A1", "AAAAAA")])
    out = asyncio.run(sync_immich.version_set(im, g, conn, CFG_MAP, "A1"))
    assert out == {"versioned": False}


def test_set_role_swaps_tag_and_cache(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO immich_version_members (gramps_id, asset_id, checksum,"
                 " role, label, seq) VALUES ('AAAAAA','A2','ck2',NULL,NULL,2)")
    conn.commit()
    a2 = {"id": "A2", "tags": [{"id": "tagOrig", "value": "Gramps/Role/Original"}]}
    im = _FakeImmich([], extra=[a2])
    out = asyncio.run(sync_immich.set_role(im, conn, "AAAAAA", "A2", "ai"))
    assert out == {"asset_id": "A2", "role": "ai"}
    # old role tag removed, new one applied
    assert ("tagOrig", ["A2"]) in im.untag_calls
    assert ("tag:Gramps/Role/AI", ["A2"]) in im.tag_calls
    row = conn.execute("SELECT role FROM immich_version_members WHERE asset_id='A2'").fetchone()
    assert row["role"] == "ai"


def test_set_role_rejects_unknown(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    im = _FakeImmich([], extra=[{"id": "A2", "tags": []}])
    try:
        asyncio.run(sync_immich.set_role(im, conn, "AAAAAA", "A2", "bogus"))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_set_label_updates_cache(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO immich_version_members (gramps_id, asset_id, checksum,"
                 " role, label, seq) VALUES ('AAAAAA','A2','ck2',NULL,NULL,2)")
    conn.commit()
    out = sync_immich.set_label(conn, "AAAAAA", "A2", "  best scan  ")
    assert out == {"asset_id": "A2", "label": "best scan"}
    row = conn.execute("SELECT label FROM immich_version_members WHERE asset_id='A2'").fetchone()
    assert row["label"] == "best scan"


def test_adopt_creates_stack_tags_and_baselines(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    im = _FakeImmich([], extra=[{"id": "A1", "checksum": "ckA1", "tags": []},
                                {"id": "A2", "checksum": "ckA2", "tags": []}])
    out = asyncio.run(sync_immich.adopt(im, conn, CFG_MAP, "AAAAAA", "A1", ["A2"]))
    assert out["primary_asset_id"] == "A1" and out["stack_id"] == "SNEW"
    assert im.created_stacks == [["A1", "A2"]]
    # baselined: row + members + tags on both
    r = _row(conn, "AAAAAA")
    assert r["current_asset_id"] == "A1" and r["member_count"] == 2
    assert [m["asset_id"] for m in _members(conn, "AAAAAA")] == ["A1", "A2"]
    assert _tagged_assets(im, "Sync/Gramps") == {"A1", "A2"}
    assert _tagged_assets(im, "Gramps/Base/AAAAAA") == {"A1", "A2"}


def test_adopt_needs_a_second_asset(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    im = _FakeImmich([], extra=[{"id": "A1", "checksum": "ckA1", "tags": []}])
    try:
        asyncio.run(sync_immich.adopt(im, conn, CFG_MAP, "AAAAAA", "A1", []))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_full_sync_does_not_recreate_version_members(tmp_path):
    # A non-displayed version member carries the sync tag (propagated), but the
    # full create-sync must NOT make a duplicate Gramps media for it.
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO immich_version_members (gramps_id, asset_id, checksum,"
                 " role, label, seq) VALUES ('AAAAAA','VER1','ck',NULL,NULL,2)")
    conn.commit()
    # VER1 is tagged (in the sync universe) but is a version, not the synced asset.
    out, g, _ = _run(conn, [_vasset("VER1")], media=[], versions_only=False)
    assert out["summary"]["created"] == 0
    assert out["created"] == []          # no NEW media event for the version member
    assert g.updated_media == []
