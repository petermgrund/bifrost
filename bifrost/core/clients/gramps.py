"""Async Gramps Web API client — the one client (seeded from control-center's,
which was itself lifted from osm-to-gramps; this is its final home).

Bearer token with auto re-auth on 401. Constructor takes explicit credentials
so the client has no import-time config dependency (testable, reusable by the
future presentation app).
"""

from __future__ import annotations

import httpx


class GrampsError(Exception):
    """Wraps any non-2xx response from Gramps Web."""


class GrampsClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base = base_url.rstrip("/")
        self._user = username
        self._pass = password
        self._client = httpx.AsyncClient(timeout=30.0)
        self._token: str | None = None

    async def __aenter__(self) -> "GrampsClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _ensure_token(self) -> None:
        if self._token:
            return
        resp = await self._client.post(
            f"{self._base}/token/",
            json={"username": self._user, "password": self._pass},
        )
        if resp.status_code >= 400:
            raise GrampsError(f"Auth failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        token = data.get("access_token") or data.get("access")
        if not token:
            raise GrampsError(f"No token in auth response: {data}")
        self._token = token

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        await self._ensure_token()
        headers = kwargs.pop("headers", {}) or {}
        headers["Authorization"] = f"Bearer {self._token}"
        resp = await self._client.request(
            method, f"{self._base}{path}", headers=headers, **kwargs
        )
        if resp.status_code == 401:
            # Token expired — drop it and retry once.
            self._token = None
            await self._ensure_token()
            headers["Authorization"] = f"Bearer {self._token}"
            resp = await self._client.request(
                method, f"{self._base}{path}", headers=headers, **kwargs
            )
        if resp.status_code >= 400:
            raise GrampsError(f"{method} {path} → {resp.status_code}: {resp.text[:500]}")
        return resp

    # --- endpoints (grown as modules need them) ---

    async def get_metadata(self) -> dict:
        """Tree/server info; cheapest authenticated call — used by doctor."""
        resp = await self._request("GET", "/metadata/")
        return resp.json()

    async def get_place(self, handle: str) -> dict:
        resp = await self._request("GET", f"/places/{handle}")
        return resp.json()

    async def list_places(self, keys: str = "handle") -> list[dict]:
        """Page through all places, returning the requested keys per place."""
        places: list[dict] = []
        page = 1
        while True:
            resp = await self._request(
                "GET", "/places/",
                params={"pagesize": 500, "page": page, "keys": keys},
            )
            items = resp.json()
            if not isinstance(items, list) or not items:
                break
            places.extend(items)
            if len(items) < 500:
                break
            page += 1
        return places
