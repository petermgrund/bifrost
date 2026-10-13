"""Record types Bifrost holds: saved versions, restoring a built-in type, deleting"""

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from bifrost.core import db
from bifrost.modules import citations, record_types
from bifrost.modules.record_types import RecordTypeError
from bifrost.web.routes.record_types import router


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "bifrost.db")
    yield c
    c.close()


DEED = {"name": "Deed", "title": "{collection}", "source": [["collection", "Collection", ""]]}


def test_each_save_is_the_next_version_and_every_version_is_kept(conn):
    first = record_types.save(conn, "my-deed", "custom", DEED)
    assert (first["version"], first["kind"], first["deleted"]) == (1, "custom", False)
    second = record_types.save(conn, "my-deed", "custom", {**DEED, "title": "{collection}, {years}"})
    assert second["version"] == 2 and second["definition"]["title"] == "{collection}, {years}"
    assert [(v["version"], v["definition"]["title"]) for v in record_types.versions(conn, "my-deed")] == [
        (1, "{collection}"), (2, "{collection}, {years}")]
    assert [t["id"] for t in record_types.list_types(conn)] == ["my-deed"]


def test_restoring_a_built_in_type_is_a_version_of_its_own(conn):
    record_types.save(conn, "us-vital", "override", {"name": "State vital record", "abbrev": "x"})
    back = record_types.restore(conn, "us-vital")
    assert (back["kind"], back["definition"], back["version"]) == ("shipped", None, 2)
    record_types.save(conn, "my-deed", "custom", DEED)
    with pytest.raises(RecordTypeError):
        record_types.restore(conn, "my-deed")


def test_deleting_keeps_the_definition_and_its_versions(conn):
    record_types.save(conn, "my-deed", "custom", DEED)
    gone = record_types.delete(conn, "my-deed", "custom")
    assert (gone["deleted"], gone["kind"], gone["definition"]["name"], gone["version"]) == (True, "custom", "Deed", 2)
    hidden = record_types.delete(conn, "pp-letter", "override")
    assert (hidden["deleted"], hidden["kind"], hidden["definition"]) == (True, "override", None)
    assert record_types.restore(conn, "pp-letter")["deleted"] is False


def test_general_form_drafts_start_new_types_newest_first(conn):
    citations.keep_draft(conn, "c1", "general", {"values": {"collection": "Deed Record"}, "subject": {"noun": "deed"}})
    citations.keep_draft(conn, "c2", "us-vital", {"values": {}})
    conn.execute("UPDATE citation_drafts SET created_at='2026-01-01T00:00:00+00:00' WHERE citation_handle='c1'")
    citations.keep_draft(conn, "c3", "general", {"values": {"collection": "Mortgage Record"}})
    assert [(d["handle"], d["draft"]["values"]["collection"]) for d in record_types.general_drafts(conn)] == [
        ("c3", "Mortgage Record"), ("c1", "Deed Record")]


@pytest.mark.parametrize("type_id, kind, definition", [
    ("Bad Id", "custom", DEED), ("my-deed", "nonsense", DEED), ("my-deed", "custom", {"title": "x"}),
    ("my-deed", "shipped", DEED)])
def test_refused_saves(conn, type_id, kind, definition):
    with pytest.raises(RecordTypeError):
        record_types.save(conn, type_id, kind, definition)
    assert record_types.list_types(conn) == []


def test_the_api_saves_lists_restores_and_deletes(conn):
    app = FastAPI()
    app.include_router(router)
    app.state.conn = conn

    async def go(method, url, **kw):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bifrost") as client:
            return await client.request(method, url, **kw)

    call = lambda *a, **kw: asyncio.run(go(*a, **kw))  # noqa: E731
    assert call("PUT", "/citations/api/types/my-deed", json={"kind": "custom", "definition": DEED}).json()["version"] == 1
    assert call("PUT", "/citations/api/types/my-deed", json={"kind": "custom", "definition": {}}).status_code == 400
    assert [t["id"] for t in call("GET", "/citations/api/types").json()["types"]] == ["my-deed"]
    assert call("POST", "/citations/api/types/my-deed/delete", json={"kind": "custom"}).json()["deleted"] is True
    assert len(call("GET", "/citations/api/types/my-deed/versions").json()["versions"]) == 2
    assert call("POST", "/citations/api/types/my-deed/restore").status_code == 400
    assert call("GET", "/citations/api/general-drafts").json() == {"drafts": []}
    page = call("GET", "/citations/types")
    assert page.status_code == 200 and "<record-types>" in page.text
