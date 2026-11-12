"""copyparty files as Gramps media: the client, the config, the sync and its webhook"""

import asyncio
import copy
import hashlib
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core import health
from bifrost.core.clients import CopypartyClient, CopypartyError
from bifrost.core.clients.gramps import GrampsClient
from bifrost.core.config import ConfigError, SyncCopypartyConfig, load_config
from bifrost.modules import check, codes, sync_copyparty
from bifrost.web.routes import sync as sync_routes

CFG = SyncCopypartyConfig(public_url="http://files", path_mappings=(("", "gda/"),), webhook_token="s3cret")


def run(coro):
    return asyncio.run(coro)


# ---- the client

def listing(files=(), dirs=(), acct="bifrost", perms=("read", "get")):
    return {"dirs": [{"href": d} for d in dirs], "files": [{"href": h, "sz": sz} for h, sz in files],
            "acct": acct, "perms": list(perms)}


def client(pages, **kw):
    """A client whose server answers ?ls from `pages` (folder -> listing) and serves `kw['files']`"""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if request.url.query == b"ls":
            page = pages.get(path)
            return httpx.Response(200, json=page) if page is not None else httpx.Response(404)
        data = (kw.get("files") or {}).get(path)
        return httpx.Response(200, content=data) if data is not None else httpx.Response(404)

    c = CopypartyClient("http://cp:3923/", kw.get("username", "bifrost"), kw.get("password", "pw"))
    c._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=c._client.headers)
    return c, seen


class TestClient:

    def test_the_login_is_the_pw_header_with_or_without_a_username(self):
        c, seen = client({"/": listing()})
        run(c.ls())
        assert seen[0].headers["PW"] == "bifrost:pw"
        c, seen = client({"/": listing()}, username="")
        run(c.ls())
        assert seen[0].headers["PW"] == "pw"
        assert "PW" not in CopypartyClient("http://cp")._client.headers

    def test_ls_asks_for_the_folder_quoted(self):
        c, seen = client({"/": listing(), "/sub dir/1962 & after/": listing()})
        run(c.ls(""))
        run(c.ls("/sub dir/1962 & after/"))
        assert [str(r.url) for r in seen] == ["http://cp:3923/?ls", "http://cp:3923/sub%20dir/1962%20%26%20after/?ls"]

    def test_a_login_copyparty_did_not_accept_is_an_error(self):
        c, _ = client({"/": listing(acct="*", perms=())})
        with pytest.raises(CopypartyError, match="not signed in") as exc:
            run(c.ls())
        assert exc.value.status == 403

    def test_an_account_without_read_access_is_an_error(self):
        c, _ = client({"/fh/": listing(perms=("write",))})
        with pytest.raises(CopypartyError, match="account bifrost cannot read /fh"):
            run(c.ls("fh"))

    def test_a_missing_folder_or_a_page_that_is_no_listing(self):
        c, _ = client({})
        with pytest.raises(CopypartyError) as exc:
            run(c.ls("nope"))
        assert exc.value.status == 404
        c, _ = client({}, files={"/": b"<html>login</html>"})
        c._client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>")))
        with pytest.raises(CopypartyError, match="did not answer with a listing"):
            run(c.ls())

    def test_account_names_who_copyparty_sees(self):
        c, _ = client({"/": listing(acct="*", perms=("read",))})
        assert run(c.account()) == "*"

    def test_walk_lists_every_file_and_skips_dotfiles_and_unfinished_uploads(self):
        pages = {
            "/": listing(files=[("6J8JDA.m4a", 5), (".hidden", 1), ("upload.mp3.PARTIAL", 9)],
                         dirs=["oral%20history/", ".hist/"]),
            "/oral history/": listing(files=[("Grandma%20%26%20Ed%2C%20%231.wav", 7)], dirs=["deep/"]),
            "/oral history/deep/": listing(files=[("x.flac", 3)]),
        }
        c, seen = client(pages)
        assert run(c.walk()) == [
            {"path": "6J8JDA.m4a", "size": 5},
            {"path": "oral history/Grandma & Ed, #1.wav", "size": 7},
            {"path": "oral history/deep/x.flac", "size": 3},
        ]
        assert len(seen) == 3
        assert [f["path"] for f in run(c.walk("/oral history/"))] == [
            "oral history/Grandma & Ed, #1.wav", "oral history/deep/x.flac"]

    def test_md5_hashes_the_file(self):
        c, seen = client({}, files={"/oral history/a b.wav": b"RIFF-bytes"})
        assert run(c.md5("oral history/a b.wav")) == hashlib.md5(b"RIFF-bytes").hexdigest()
        assert str(seen[0].url) == "http://cp:3923/oral%20history/a%20b.wav"
        with pytest.raises(CopypartyError):
            run(c.md5("gone.wav"))


# ---- the config

BASE = """\
gramps: {base_url: "http://g/api", username: u, password: p}
paperless: {base_url: "http://p", api_token: t}
"""


def _load(tmp_path, extra):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(BASE + extra)
    return load_config(cfg)


class TestConfig:

    def test_absent_is_off(self, tmp_path):
        cfg = _load(tmp_path, "")
        assert cfg.copyparty.base_url == "" and cfg.sync_copyparty.path_mappings == ()

    def test_folders_prefixes_and_the_link_address(self, tmp_path):
        cfg = _load(tmp_path, """\
copyparty: {base_url: "http://eir:3923/", username: bifrost, password: pw}
sync:
  copyparty:
    webhook_token: " tok "
    path_mappings:
      - {copyparty_prefix: "/", gramps_prefix: "gda-files/"}
""")
        assert (cfg.copyparty.base_url, cfg.copyparty.username, cfg.copyparty.password) == (
            "http://eir:3923", "bifrost", "pw")
        assert cfg.sync_copyparty == SyncCopypartyConfig(
            public_url="http://eir:3923", path_mappings=(("", "gda-files/"),), webhook_token="tok")
        cfg = _load(tmp_path, """\
copyparty: {base_url: "http://eir:3923"}
sync:
  copyparty:
    public_url: "https://files.example/"
    path_mappings:
      - {copyparty_prefix: "/fh/audio/", gramps_prefix: "/copyparty"}
      - {copyparty_prefix: maps, gramps_prefix: maps/}
""")
        assert cfg.sync_copyparty.public_url == "https://files.example"
        assert cfg.sync_copyparty.path_mappings == (("fh/audio", "copyparty/"), ("maps", "maps/"))

    @pytest.mark.parametrize("mappings", [
        '[{copyparty_prefix: "/"}]',
        '[{copyparty_prefix: "/", gramps_prefix: "/"}]',
        '["/fh"]',
        '[{copyparty_prefix: "/", gramps_prefix: a}, {copyparty_prefix: fh, gramps_prefix: b}]',
        '[{copyparty_prefix: fh, gramps_prefix: a}, {copyparty_prefix: fh/audio, gramps_prefix: b}]',
    ])
    def test_refusals(self, tmp_path, mappings):
        with pytest.raises(ConfigError):
            _load(tmp_path, f"sync:\n  copyparty:\n    path_mappings: {mappings}\n")


# ---- the sync

def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


class Copyparty:
    def __init__(self, files=None, down=False):
        self.files = dict(files or {})
        self.down = down
        self.hashed = []

    async def walk(self, folder=""):
        if self.down:
            raise CopypartyError("not signed in (check copyparty.username and password) cannot read /", 403)
        return [{"path": p, "size": len(b)} for p, b in sorted(self.files.items())
                if not folder or p.startswith(f"{folder}/")]

    async def md5(self, path):
        self.hashed.append(path)
        return md5(self.files[path])


class Gramps:
    def __init__(self, media=(), withdrawn=""):
        self.media = {m["gramps_id"]: m for m in media}
        self.withdrawn = withdrawn
        self.created = []
        self.updated = []
        self.bytes = {}
        self.unreadable = False

    async def list_media(self, keys=None):
        return copy.deepcopy(list(self.media.values()))

    async def get_media_by_gramps_id(self, gid, backlinks=False, notes=False):
        return copy.deepcopy(self.media.get(gid))

    async def find_notes(self, note_type):
        if not self.withdrawn:
            return []
        return [{"handle": "wn", "gramps_id": "N0001", "type": note_type, "text": {"string": self.withdrawn}}]

    async def create_media(self, obj):
        self.media[obj["gramps_id"]] = obj
        self.created.append(obj["gramps_id"])

    async def update_media(self, handle, obj):
        self.media[obj["gramps_id"]] = obj
        self.updated.append(obj["gramps_id"])

    async def media_md5(self, handle):
        if self.unreadable:
            raise RuntimeError("GET /media/h/file → 404")
        media = next(m for m in self.media.values() if m["handle"] == handle)
        return md5(self.bytes.get(media["path"], media["path"].encode()))

    store_checksum = GrampsClient.store_checksum


def attr(name, value):
    return {"_class": "Attribute", "type": name, "value": value, "private": False,
            "citation_list": [], "note_list": []}


def synced(gid, path, data=None, desc=None, links=None):
    """A media object whose file is the copyparty file at `path`"""
    urls = [f"http://files/{path}".replace(" ", "%20")] if links is None else links
    return {"gramps_id": gid, "handle": f"h-{gid}", "desc": desc or path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
            "path": f"gda/{path}", "mime": "audio/mp4", "checksum": md5(data or f"gda/{path}".encode()),
            "attribute_list": [attr("Copyparty URL", u) for u in urls]}


def document(gid, extra=()):
    return {"gramps_id": gid, "handle": f"h-{gid}", "desc": "Transcript", "path": "paperless/0001398.pdf",
            "mime": "application/pdf", "checksum": "abc",
            "attribute_list": [attr("Paperless URL", "http://p/documents/1398/details"),
                               attr("Paperless ID", "1398"), *extra]}


def sync(cp, gr, apply=True, cfg=CFG, selected=None):
    async def collect():
        return [e async for e in sync_copyparty.sync(cp, gr, cfg, apply=apply, selected=selected)]
    return run(collect())


def items(events):
    return [e for e in events if e.kind == "item"]


def summary(events):
    return next(e for e in events if e.kind == "summary").data


def links(media):
    return [a["value"] for a in media["attribute_list"] if a["type"] == "Copyparty URL"]


class TestHelpers:

    def test_mime_of_knows_the_audio_types_python_does_not(self):
        assert sync_copyparty.mime_of("6J8JDA.m4a") == "audio/mp4"
        assert sync_copyparty.mime_of("a.FLAC") == "audio/flac"
        assert sync_copyparty.mime_of("a.mp3") == "audio/mpeg"
        assert sync_copyparty.mime_of("county.geojson") == "application/geo+json"
        assert sync_copyparty.mime_of("mystery.zzz") == "application/octet-stream"

    def test_file_of_maps_the_folder_and_reads_a_code_from_the_name(self):
        f = sync_copyparty.file_of("fh/oral history/Grandma & Ed.wav", "fh", "copyparty/", "http://files")
        assert f["gramps_path"] == "copyparty/oral history/Grandma & Ed.wav"
        assert f["url"] == "http://files/fh/oral%20history/Grandma%20%26%20Ed.wav"
        assert (f["name"], f["stem"], f["code"]) == ("Grandma & Ed.wav", "Grandma & Ed", None)
        assert sync_copyparty.file_of("6J8JDA.m4a", "", "gda/", "http://files")["code"] == "6J8JDA"
        for name in ("summer.mp3", "6j8jda.m4a", "ABCDEFG.wav", "222222.wav", "ABCDEI.wav"):
            assert sync_copyparty.file_of(name, "", "gda/", "http://files")["code"] is None


class TestCreate:

    def test_preview_writes_nothing(self):
        cp, gr = Copyparty({"Interview 1962.m4a": b"audio"}), Gramps()
        events = sync(cp, gr, apply=False)
        (row,) = items(events)
        assert (row.entity, row.action, row.source_id, row.title) == (
            "file", "would_create", "Interview 1962.m4a", "Interview 1962.m4a")
        assert row.data == {"cols": {"title": "Interview 1962"}}
        assert gr.media == {} and summary(events)["created"] == 1 and cp.hashed == []

    def test_a_new_file_becomes_a_media_object_pointing_at_it(self, script_ids):
        script_ids("FRESH2")
        cp, gr = Copyparty({"oral history/Interview 1962.m4a": b"audio"}), Gramps()
        gr.bytes["gda/oral history/Interview 1962.m4a"] = b"audio"
        events = sync(cp, gr)
        (row,) = items(events)
        assert (row.action, row.gramps_id) == ("created", "FRESH2")
        media = gr.media["FRESH2"]
        assert (media["desc"], media["path"], media["mime"]) == (
            "Interview 1962", "gda/oral history/Interview 1962.m4a", "audio/mp4")
        assert links(media) == ["http://files/oral%20history/Interview%201962.m4a"]
        assert media["checksum"] == md5(b"audio")
        assert summary(events) == {"created": 1, "files_moved": 0, "files_linked": 0, "errors": 0}
        assert items(sync(cp, gr)) == []

    def test_only_files_under_a_mapped_folder_are_synced(self):
        cfg = SyncCopypartyConfig(public_url="http://files", path_mappings=(("fh", "copyparty/"),))
        cp, gr = Copyparty({"fh/a.wav": b"1", "private/dna.csv": b"2", "fhx/b.wav": b"3"}), Gramps()
        sync(cp, gr, cfg=cfg)
        (media,) = gr.media.values()
        assert media["path"] == "copyparty/a.wav" and links(media) == ["http://files/fh/a.wav"]

    def test_a_file_named_with_a_free_code_takes_it(self):
        cp, gr = Copyparty({"6J8JDA.m4a": b"audio"}), Gramps()
        preview = sync(cp, gr, apply=False)
        assert items(preview)[0].gramps_id == "6J8JDA"
        sync(cp, gr)
        assert list(gr.media) == ["6J8JDA"] and gr.media["6J8JDA"]["desc"] == "6J8JDA"

    def test_a_generated_code_never_takes_one_a_file_is_named_with(self, script_ids):
        script_ids("ABC234", "FRESH2")
        cp, gr = Copyparty({"interview.wav": b"1", "later/ABC234.wav": b"2"}), Gramps()
        sync(cp, gr)
        assert {m["gramps_id"]: m["desc"] for m in gr.media.values()} == {"FRESH2": "interview", "ABC234": "ABC234"}

    def test_a_withdrawn_code_is_a_failed_row(self):
        cp, gr = Copyparty({"WDRN22.m4a": b"audio"}), Gramps(withdrawn="WDRN22 2026-01-01 lost")
        for apply in (False, True):
            events = sync(cp, gr, apply=apply)
            (row,) = items(events)
            assert row.action == "failed" and "withdrawn on 2026-01-01" in row.detail
            assert gr.media == {} and summary(events)["errors"] == 1

    def test_a_file_gramps_cannot_read_is_reported(self):
        cp, gr = Copyparty({"a.wav": b"1"}), Gramps()
        gr.unreadable = True
        events = sync(cp, gr)
        assert [e.action for e in items(events)] == ["created", "failed"]
        assert "could not read its file" in items(events)[1].detail and len(gr.media) == 1

    def test_selected_limits_an_apply(self):
        cp, gr = Copyparty({"a.wav": b"1", "b.wav": b"2"}), Gramps()
        events = sync(cp, gr, selected={"file:b.wav"})
        assert [e.source_id for e in items(events)] == ["b.wav"]
        assert [m["desc"] for m in gr.media.values()] == ["b"]


class TestLinks:

    def test_a_file_named_after_a_documents_code_is_linked_from_it(self):
        cp, gr = Copyparty({"6J3Z5Z.m4a": b"audio"}), Gramps([document("6J3Z5Z")])
        preview = sync(cp, gr, apply=False)
        (row,) = items(preview)
        assert (row.entity, row.action, row.source_id, row.gramps_id, row.title) == (
            "media", "would_update", "6J3Z5Z", "6J3Z5Z", "Transcript")
        assert row.data == {"cols": {"link": "6J3Z5Z.m4a"}} and gr.updated == []
        events = sync(cp, gr)
        assert [e.action for e in items(events)] == ["updated"] and gr.created == []
        media = gr.media["6J3Z5Z"]
        assert media["path"] == "paperless/0001398.pdf"
        assert [a["type"] for a in media["attribute_list"]] == ["Paperless URL", "Paperless ID", "Copyparty URL"]
        assert links(media) == ["http://files/6J3Z5Z.m4a"]
        assert summary(events)["files_linked"] == 1
        assert items(sync(cp, gr)) == [] and cp.hashed == []

    def test_two_files_with_one_new_code_make_one_media_object(self):
        cp, gr = Copyparty({"ABC234.m4a": b"1", "ABC234.wav": b"2"}), Gramps()
        events = sync(cp, gr)
        assert [(e.action, e.source_id) for e in items(events)] == [("created", "ABC234.m4a")]
        media = gr.media["ABC234"]
        assert media["path"] == "gda/ABC234.m4a"
        assert links(media) == ["http://files/ABC234.m4a", "http://files/ABC234.wav"]
        assert items(sync(cp, gr)) == []

    def test_a_link_whose_file_is_gone_is_removed(self):
        stale = document("6J3Z5Z", extra=[attr("Copyparty URL", "http://files/6J3Z5Z.m4a")])
        cp, gr = Copyparty({}), Gramps([stale])
        events = sync(cp, gr)
        (row,) = items(events)
        assert row.data == {"cols": {"link": "removed"}}
        assert links(gr.media["6J3Z5Z"]) == [] and len(gr.media["6J3Z5Z"]["attribute_list"]) == 2

    def test_a_changed_address_rewrites_the_links(self):
        cp, gr = Copyparty({"a.wav": b"1"}), Gramps([synced("ABC234", "a.wav", links=["http://old/a.wav"])])
        events = sync(cp, gr)
        (row,) = items(events)
        assert (row.entity, row.source_id) == ("file", "a.wav")
        assert links(gr.media["ABC234"]) == ["http://files/a.wav"]


class TestMoves:

    def test_a_moved_file_is_followed_by_its_bytes(self):
        cp = Copyparty({"oral history/interview.m4a": b"audio"})
        gr = Gramps([synced("ABC234", "interview.m4a", data=b"audio")])
        gr.bytes["gda/oral history/interview.m4a"] = b"audio"
        preview = sync(cp, gr, apply=False)
        (row,) = items(preview)
        assert (row.action, row.gramps_id, row.source_id) == ("would_update", "ABC234", "oral history/interview.m4a")
        assert row.data == {"cols": {"file": "gda/interview.m4a → gda/oral history/interview.m4a"}}
        assert gr.updated == [] and summary(preview)["files_moved"] == 1
        events = sync(cp, gr)
        media = gr.media["ABC234"]
        assert media["path"] == "gda/oral history/interview.m4a" and media["checksum"] == md5(b"audio")
        assert links(media) == ["http://files/oral%20history/interview.m4a"]
        assert gr.created == [] and summary(events)["files_moved"] == 1
        assert items(sync(cp, gr)) == []

    def test_a_renamed_file_retitles_only_an_untouched_title(self):
        cp = Copyparty({"Grandma 1962.m4a": b"audio"})
        gr = Gramps([synced("ABC234", "interview.m4a", data=b"audio")])
        sync(cp, gr)
        assert gr.media["ABC234"]["desc"] == "Grandma 1962"
        cp = Copyparty({"Grandma 1962 (edited).m4a": b"audio"})
        gr = Gramps([synced("ABC234", "interview.m4a", data=b"audio", desc="Interview with Grandma")])
        sync(cp, gr)
        assert gr.media["ABC234"]["desc"] == "Interview with Grandma"
        assert gr.media["ABC234"]["path"] == "gda/Grandma 1962 (edited).m4a"

    def test_a_file_renamed_to_its_code_is_followed_without_reading_it(self):
        cp = Copyparty({"ABC234.m4a": b"new bytes"})
        gr = Gramps([synced("ABC234", "interview.m4a", data=b"audio", desc="Interview")])
        events = sync(cp, gr)
        assert [e.action for e in items(events)] == ["updated"] and cp.hashed == []
        assert gr.media["ABC234"]["path"] == "gda/ABC234.m4a" and gr.media["ABC234"]["desc"] == "Interview"

    def test_different_bytes_are_a_new_file_and_the_old_media_is_reported(self, script_ids):
        script_ids("FRESH2")
        cp = Copyparty({"other.m4a": b"something else"})
        gr = Gramps([synced("ABC234", "interview.m4a", data=b"audio")])
        events = sync(cp, gr)
        assert [(e.action, e.gramps_id) for e in items(events)] == [("created", "FRESH2"), ("failed", "ABC234")]
        gone = items(events)[1]
        assert (gone.source_id, gone.detail) == ("gda/interview.m4a", "its file is gone from copyparty")
        assert gr.media["ABC234"]["path"] == "gda/interview.m4a" and summary(events)["errors"] == 1

    def test_nothing_is_downloaded_while_every_media_has_its_file(self):
        cp = Copyparty({"interview.m4a": b"audio", "new.m4a": b"new"})
        sync(cp, Gramps([synced("ABC234", "interview.m4a", data=b"audio")]), apply=False)
        assert cp.hashed == []

    def test_a_missing_checksum_is_filled(self):
        media = synced("ABC234", "a.wav")
        media["checksum"] = ""
        cp, gr = Copyparty({"a.wav": b"1"}), Gramps([media])
        preview = sync(cp, gr, apply=False)
        assert items(preview)[0].data == {"cols": {"checksum": "missing"}}
        sync(cp, gr)
        assert gr.media["ABC234"]["checksum"] == md5(b"gda/a.wav")


class TestFailures:

    def test_copyparty_down_is_an_error_event_and_nothing_is_reported_gone(self):
        gr = Gramps([synced("ABC234", "a.wav")])
        events = sync(Copyparty(down=True), gr)
        assert [e.kind for e in events] == ["error", "summary"]
        assert events[0].detail.startswith("copyparty: not signed in") and summary(events)["errors"] == 1

    def test_gramps_down_is_an_error_event(self):
        class Down(Gramps):
            async def list_media(self, keys=None):
                raise RuntimeError("502 bad gateway")

        events = sync(Copyparty({"a.wav": b"1"}), Down())
        assert [e.kind for e in events] == ["error", "summary"] and "Gramps could not be read" in events[0].detail


# ---- the webhook

WEBHOOK = "/sync/api/copyparty/webhook"
TOKEN = {"X-Bifrost-Token": "s3cret"}


def make_app(cp, gr, cfg=CFG):
    app = FastAPI()
    app.include_router(sync_routes.router)
    app.state.copyparty = cp
    app.state.gramps = gr
    app.state.caches = {"stale": True}
    app.state.cfg = SimpleNamespace(sync_copyparty=cfg)
    return app


def call(app, **kw):
    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://bifrost") as c:
            resp = await c.post(WEBHOOK, **kw)
        await asyncio.gather(*getattr(app.state, "webhook_tasks", ()))
        return resp
    return run(go())


class TestWebhook:

    def test_off_without_copyparty_a_folder_or_a_token(self):
        gr = Gramps()
        assert call(make_app(None, gr), headers=TOKEN).status_code == 404
        assert call(make_app(Copyparty(), gr, SyncCopypartyConfig(webhook_token="s3cret")), headers=TOKEN).status_code == 404
        no_token = SyncCopypartyConfig(path_mappings=(("", "gda/"),))
        assert call(make_app(Copyparty(), gr, no_token), headers=TOKEN).status_code == 404

    def test_rejects_a_missing_or_wrong_token(self):
        app = make_app(Copyparty({"a.wav": b"1"}), Gramps())
        assert call(app).status_code == 403
        assert call(app, headers={"X-Bifrost-Token": "nope"}).status_code == 403
        assert app.state.gramps.media == {}

    def test_a_hook_syncs_the_folders(self):
        gr = Gramps()
        app = make_app(Copyparty({"a.wav": b"1"}), gr)
        r = call(app, headers=TOKEN)
        assert r.status_code == 202 and r.json() == {"queued": True}
        assert [m["desc"] for m in gr.media.values()] == ["a"] and app.state.caches == {}

    def test_hooks_arriving_together_share_a_run(self):
        class Gated(Copyparty):
            def __init__(self, files):
                super().__init__(files)
                self.gate = asyncio.Event()
                self.walks = 0

            async def walk(self, folder=""):
                self.walks += 1
                await self.gate.wait()
                return await super().walk(folder)

        async def settle():
            for _ in range(3):
                await asyncio.sleep(0)

        async def go(first_starts: bool):
            cp = Gated({"a.wav": b"1"})
            app = make_app(cp, Gramps())
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://bifrost") as c:
                statuses = [(await c.post(WEBHOOK, headers=TOKEN)).status_code]
                if first_starts:
                    await settle()
                statuses += [(await c.post(WEBHOOK, headers=TOKEN)).status_code for _ in range(4)]
                await settle()
                cp.gate.set()
                while app.state.webhook_tasks:
                    await asyncio.gather(*app.state.webhook_tasks)
                    await settle()
            return statuses, cp.walks

        assert run(go(first_starts=False)) == ([202] * 5, 1)
        assert run(go(first_starts=True)) == ([202] * 5, 2)


# ---- the check, the Codes list and the status page

def test_the_check_runs_copyparty_when_it_is_configured(monkeypatch):
    from bifrost.core.config import GeminiConfig, SyncImmichConfig, SyncPaperlessConfig
    from bifrost.core.events import SyncEvent

    def part(name, calls):
        async def gen(*args, **kwargs):
            calls.append(name)
            yield SyncEvent(kind="summary", data={name: 1})
        return gen

    calls = []
    monkeypatch.setattr(check, "sync_paperless", SimpleNamespace(sync=part("paperless", calls)))
    monkeypatch.setattr(check, "sync_copyparty", SimpleNamespace(sync=part("copyparty", calls)))
    cfg = SimpleNamespace(sync_paperless=SyncPaperlessConfig(), sync_immich=SyncImmichConfig(),
                          gemini=GeminiConfig(), sync_copyparty=CFG)

    async def collect(copyparty, config):
        return [e async for e in check.run("gramps", "paperless", "gemini", [], config, apply=False,
                                           copyparty=copyparty)]

    events = run(collect("copyparty", cfg))
    assert calls == ["paperless", "copyparty"] and events[-1].data == {"paperless": 1, "copyparty": 1}
    calls.clear()
    run(collect(None, cfg))
    cfg.sync_copyparty = SyncCopypartyConfig()
    run(collect("copyparty", cfg))
    assert calls == ["paperless", "paperless"]


def test_codes_rows_show_the_files():
    media = [synced("6J8JDA", "6J8JDA.m4a", desc="Slideshow audio"),
             document("6J3Z5Z", extra=[attr("Copyparty URL", "http://files/oral%20history/6J3Z5Z.m4a")]),
             {**synced("CSVF22", "notes.csv"), "mime": "text/csv"}]
    rows = {r["code"]: r for r in codes.rows(media, {})}
    assert rows["6J8JDA"]["type"] == "audio"
    assert rows["6J8JDA"]["files"] == [{"name": "6J8JDA.m4a", "url": "http://files/6J8JDA.m4a"}]
    assert rows["6J3Z5Z"]["type"] == "document" and rows["6J3Z5Z"]["paperless"][0]["id"] == "1398"
    assert rows["6J3Z5Z"]["files"] == [{"name": "6J3Z5Z.m4a", "url": "http://files/oral%20history/6J3Z5Z.m4a"}]
    assert rows["CSVF22"]["type"] == "file"
    assert [r["code"] for r in codes.search(list(rows.values()), "6j3z5z.m4a")] == ["6J3Z5Z"]


def test_the_status_page_reports_copyparty():
    class G:
        async def get_metadata(self):
            return {"gramps_webapi": {"version": "3.24.0"}}

    class P:
        async def version(self):
            return "3.3.3"

    class C:
        def __init__(self, acct=None):
            self.acct, self.asked = acct, []

        async def account(self, folder=""):
            self.asked.append(folder)
            if self.acct is None:
                raise CopypartyError("not signed in (check copyparty.username and password) cannot read /fh", 403)
            return self.acct

    ok = C("bifrost")
    rows = run(health.probe_services(G(), P(), [], ok, "fh"))
    row = next(r for r in rows if r["key"] == "copyparty")
    assert row == {"key": "copyparty", "name": "copyparty", "ok": True, "detail": "account bifrost"} and ok.asked == ["fh"]
    assert next(r for r in run(health.probe_services(G(), P(), [], C("*"))) if r["key"] == "copyparty")["detail"] == "open to everyone"
    bad = next(r for r in run(health.probe_services(G(), P(), [], C())) if r["key"] == "copyparty")
    assert bad["ok"] is False and "not signed in" in bad["detail"]
    assert all(r["key"] != "copyparty" for r in run(health.probe_services(G(), P(), [])))
