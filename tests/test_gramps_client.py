import asyncio
import hashlib

import httpx

from bifrost.core.clients.gramps import GrampsClient


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
