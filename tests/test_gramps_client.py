import asyncio
import hashlib
import json

import httpx
import pytest

from bifrost.core.clients.gramps import GrampsClient, GrampsError


def _client(answer):
    """A client whose Gramps answers every request but the login with answer(request)"""
    def serve(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        return answer(request)

    client = GrampsClient("http://gramps/api", "u", "p")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    return client


def test_media_md5_hashes_the_served_file_and_survives_an_expired_token():
    tokens = iter(["stale", "fresh"])

    def serve(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": next(tokens)})
        assert request.url.path == "/api/media/h1/file"
        if request.headers["Authorization"] == "Bearer stale":
            return httpx.Response(401)
        return httpx.Response(200, content=b"scan bytes" * 10_000)

    client = GrampsClient("http://gramps/api", "u", "p")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    digest = asyncio.run(client.media_md5("h1"))
    assert digest == hashlib.md5(b"scan bytes" * 10_000).hexdigest()


def test_store_checksum_writes_only_a_changed_value():
    client = GrampsClient("http://gramps/api", "u", "p")
    writes = []

    async def media_md5(handle):
        return "abc"

    async def update_media(handle, media):
        writes.append(dict(media))

    client.media_md5 = media_md5
    client.update_media = update_media
    media = {"handle": "h1", "checksum": ""}
    assert asyncio.run(client.store_checksum(media)) is True
    assert asyncio.run(client.store_checksum(media)) is False
    assert writes == [{"handle": "h1", "checksum": "abc"}]


def test_upload_media_posts_the_raw_file_and_returns_the_new_handle():
    seen = []

    def answer(request):
        seen.append((request.method, request.url.path, request.headers["Content-Type"], request.content))
        return httpx.Response(201, json=[
            {"_class": "Media", "handle": "new1", "type": "add", "old": None, "new": {}}])

    handle = asyncio.run(_client(answer).upload_media(b'{"type":"Feature"}', "application/geo+json"))
    assert handle == "new1"
    assert seen == [("POST", "/api/media/", "application/geo+json", b'{"type":"Feature"}')]


def test_replace_media_file_keeps_the_handle_and_reads_409_as_unchanged():
    statuses = iter([200, 409, 500])
    seen = []

    def answer(request):
        seen.append((request.method, request.url.path, request.headers["Content-Type"]))
        return httpx.Response(next(statuses), json=[])

    client = _client(answer)

    async def go():
        results = [await client.replace_media_file("h1", b"{}", "application/geo+json") for _ in range(2)]
        with pytest.raises(GrampsError):
            await client.replace_media_file("h1", b"{}", "application/geo+json")
        return results

    assert asyncio.run(go()) == [True, False]
    assert set(seen) == {("PUT", "/api/media/h1/file", "application/geo+json")}


def test_find_media_by_checksum_asks_for_backlinks():
    def answer(request):
        assert request.url.path == "/api/media/"
        assert request.url.params["gql"] == 'checksum="abc"'
        assert request.url.params["backlinks"] == "true"
        return httpx.Response(200, json=[{"handle": "m1", "backlinks": {}}])

    assert asyncio.run(_client(answer).find_media_by_checksum("abc")) == [{"handle": "m1", "backlinks": {}}]


def test_update_place_drops_keys_outside_the_place_schema():
    bodies = []

    def answer(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=[])

    place = {"handle": "p1", "gramps_id": "P0009", "type": "Unknown", "place_type": "State", "urls": []}
    asyncio.run(_client(answer).update_place("p1", place))
    assert bodies == [{"handle": "p1", "gramps_id": "P0009", "place_type": "State", "urls": []}]
    assert place["type"] == "Unknown"
