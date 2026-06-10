"""Async Immich API client (x-api-key auth)."""

from __future__ import annotations

import httpx


class ImmichError(Exception):
    """Wraps any non-2xx response from Immich."""


class ImmichClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=30.0, headers={"x-api-key": api_key, "Accept": "application/json"}
        )

    async def __aenter__(self) -> "ImmichClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = await self._client.request(method, f"{self._base}{path}", **kwargs)
        if resp.status_code >= 400:
            raise ImmichError(f"{method} {path} → {resp.status_code}: {resp.text[:500]}")
        return resp

    # --- endpoints (grown as modules need them) ---

    async def get_me(self) -> dict:
        """Authenticated identity check — used by doctor."""
        resp = await self._request("GET", "/api/users/me")
        return resp.json()

    async def list_people(self, with_hidden: bool = True) -> list[dict]:
        people: list[dict] = []
        page = 1
        while True:
            resp = await self._request(
                "GET", "/api/people",
                params={"page": page, "size": 500, "withHidden": str(with_hidden).lower()},
            )
            data = resp.json()
            people.extend(data.get("people", []))
            if not data.get("hasNextPage"):
                break
            page += 1
        return people

    async def get_faces(self, asset_id: str) -> list[dict]:
        resp = await self._request("GET", "/api/faces", params={"id": asset_id})
        return resp.json()

    async def get_asset(self, asset_id: str) -> dict:
        resp = await self._request("GET", f"/api/assets/{asset_id}")
        return resp.json()

    async def person_thumbnail(self, person_id: str) -> tuple[bytes, str]:
        resp = await self._request("GET", f"/api/people/{person_id}/thumbnail")
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")

    async def asset_thumbnail(self, asset_id: str, size: str = "thumbnail") -> tuple[bytes, str]:
        resp = await self._request(
            "GET", f"/api/assets/{asset_id}/thumbnail", params={"size": size}
        )
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")

    async def list_tags(self) -> list[dict]:
        resp = await self._request("GET", "/api/tags")
        return resp.json()

    async def resolve_tag_id(self, value: str) -> str | None:
        """Find a tag id by its full path value or name, case-insensitively."""
        wanted = value.lower()
        for t in await self.list_tags():
            if t.get("value", "").lower() == wanted or t.get("name", "").lower() == wanted:
                return t["id"]
        return None

    async def search_asset_ids_by_tag(self, tag_id: str) -> set[str]:
        ids: set[str] = set()
        page = 1
        while True:
            resp = await self._request(
                "POST", "/api/search/metadata",
                json={"tagIds": [tag_id], "size": 1000, "page": page},
            )
            data = resp.json()
            assets = data.get("assets", {})
            ids.update(item["id"] for item in assets.get("items", []))
            if not assets.get("nextPage"):
                break
            page += 1
        return ids

    async def tag_assets(self, tag_id: str, asset_ids: list[str]) -> list[dict]:
        resp = await self._request(
            "PUT", f"/api/tags/{tag_id}/assets", json={"ids": asset_ids}
        )
        return resp.json() if resp.content else []

    async def untag_assets(self, tag_id: str, asset_ids: list[str]) -> list[dict]:
        resp = await self._request(
            "DELETE", f"/api/tags/{tag_id}/assets", json={"ids": asset_ids}
        )
        return resp.json() if resp.content else []
