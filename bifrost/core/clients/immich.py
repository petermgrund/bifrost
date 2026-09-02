"""The single Immich API adapter"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

log = logging.getLogger("bifrost.immich")

_UUID_RE = re.compile(
    r"\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)


class ImmichError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Immich {status}: {message}")
        self.status = status
        self.message = message


def valid_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value or ""))


def _checked_id(value: str) -> str:
    if not valid_uuid(value):
        raise ImmichError(400, f"invalid id: {value!r}")
    return value


class ImmichClient:
    def __init__(self, base_url: str, api_key: str):
        self._http = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/api",
            headers={"x-api-key": api_key, "Accept": "application/json"},
            timeout=httpx.Timeout(30.0),
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            resp = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ImmichError(0, f"request failed: {exc}") from exc
        if resp.status_code >= 400:
            try:
                data = resp.json()
            except ValueError:
                data = None
            detail = (data.get("message") if isinstance(data, dict) else None) or resp.text
            raise ImmichError(resp.status_code, str(detail)[:300])
        return resp

    async def get_me(self) -> dict:
        return (await self._request("GET", "/users/me")).json()

    async def server_version(self) -> str:
        v = (await self._request("GET", "/server/version")).json()
        return ".".join(str(v.get(k, 0)) for k in ("major", "minor", "patch"))

    async def search_assets(
        self,
        page: int = 1,
        size: int = 60,
        person_id: str | None = None,
        filename: str | None = None,
        order: str = "desc",
        tag_id: str | None = None,
    ) -> dict:
        body: dict = {
            "page": page, "size": size, "order": order,
            "withStacked": True, "withExif": True,
        }
        if person_id:
            body["personIds"] = [_checked_id(person_id)]
        if filename:
            body["originalFileName"] = filename
        if tag_id:
            body["tagIds"] = [_checked_id(tag_id)]
        data = (await self._request("POST", "/search/metadata", json=body)).json()
        assets = data.get("assets") or {}
        #  v3.0.1 reports nextPage as a string
        next_page = assets.get("nextPage")
        return {
            "items": assets.get("items") or [],
            "nextPage": int(next_page) if next_page is not None else None,
        }

    async def get_asset(self, asset_id: str) -> dict:
        return (await self._request("GET", f"/assets/{_checked_id(asset_id)}")).json()

    async def get_assets_many(self, asset_ids: list[str], concurrency: int = 8) -> dict:
        """Asset detail per id -> {asset_id: dict | None}. none marks  failed"""
        semaphore = asyncio.Semaphore(concurrency)

        async def one(asset_id: str) -> tuple[str, dict | None]:
            async with semaphore:
                try:
                    return asset_id, await self.get_asset(asset_id)
                except ImmichError as exc:
                    log.warning("asset detail fetch failed for %s: %s", asset_id, exc)
                    return asset_id, None

        return dict(await asyncio.gather(*(one(a) for a in asset_ids)))

    async def get_faces(self, asset_id: str) -> list[dict]:
        return (await self._request("GET", "/faces", params={"id": _checked_id(asset_id)})).json()

    async def list_tags(self) -> list[dict]:
        return (await self._request("GET", "/tags")).json()

    async def find_tag(self, name: str) -> dict | None:
        """The tag whose full path matches `name` case insensitively or none"""
        wanted = (name or "").strip().lower()
        if not wanted:
            return None
        for tag in await self.list_tags():
            if (tag.get("value") or "").lower() == wanted:
                return tag
        return None

    async def upsert_tag(self, path: str) -> dict:
        """Create (or fetch) a hierarchical tag by its full path; Immich
        creates missing parents, so 'ID/ABC123' also makes the 'ID' tag"""
        tags = (await self._request("PUT", "/tags", json={"tags": [path]})).json()
        wanted = path.strip().lower()
        for tag in tags or []:
            if (tag.get("value") or "").lower() == wanted:
                return tag
        if not tags:
            raise ImmichError(502, f"tag upsert returned nothing for {path!r}")
        return tags[0]

    async def tag_asset(self, tag_id: str, asset_id: str) -> None:
        await self._request(
            "PUT", f"/tags/{_checked_id(tag_id)}/assets",
            json={"ids": [_checked_id(asset_id)]})

    async def untag_asset(self, tag_id: str, asset_id: str) -> None:
        await self._request(
            "DELETE", f"/tags/{_checked_id(tag_id)}/assets",
            json={"ids": [_checked_id(asset_id)]})

    async def list_stacks(self) -> list[dict]:
        return (await self._request("GET", "/stacks")).json()

    async def list_people(self, with_hidden: bool = True) -> list[dict]:
        people: list[dict] = []
        page = 1
        while True:
            data = (await self._request(
                "GET", "/people",
                params={"page": page, "size": 500,
                        "withHidden": "true" if with_hidden else "false"},
            )).json()
            people.extend(data.get("people") or [])
            if not data.get("hasNextPage"):
                return people
            page += 1

    async def get_person(self, person_id: str) -> dict:
        """Direct person fetch; resolves people the listing omits (v3.0.1)"""
        return (await self._request(
            "GET", f"/people/{_checked_id(person_id)}")).json()

    async def person_thumbnail(self, person_id: str) -> tuple[bytes, str]:
        resp = await self._request(
            "GET", f"/people/{_checked_id(person_id)}/thumbnail")
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")

    async def asset_thumbnail(self, asset_id: str) -> tuple[bytes, str]:
        resp = await self._request(
            "GET", f"/assets/{_checked_id(asset_id)}/thumbnail",
            params={"size": "thumbnail"})
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")

    async def preview_file(self, asset_id: str) -> tuple[str, str] | None:
        """(extension, mime) of the asset's preview rendition, None when Immich has none"""
        try:
            resp = await self._request(
                "HEAD", f"/assets/{_checked_id(asset_id)}/thumbnail",
                params={"size": "preview"})
        except ImmichError as exc:
            if exc.status == 404:
                return None
            raise
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        return ("webp" if mime == "image/webp" else "jpeg"), mime
