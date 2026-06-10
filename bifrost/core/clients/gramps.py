"""Async Gramps Web API client — the one client (seeded from control-center's,
which was itself lifted from osm-to-gramps; this is its final home).

Bearer token with auto re-auth on 401 and retry on a rate-limited /token/.
Constructor takes explicit credentials so the client has no import-time config
dependency (testable, reusable by the future presentation app).
"""

from __future__ import annotations

import asyncio

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
        self._auth_lock = asyncio.Lock()

    async def __aenter__(self) -> "GrampsClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _ensure_token(self) -> None:
        if self._token:
            return
        # Serialize so a concurrent burst logs in once, and retry politely on
        # 429 — Gramps Web rate-limits its /token/ endpoint.
        async with self._auth_lock:
            if self._token:
                return
            for attempt in range(4):
                resp = await self._client.post(
                    f"{self._base}/token/",
                    json={"username": self._user, "password": self._pass},
                )
                if resp.status_code == 429 and attempt < 3:
                    wait = float(resp.headers.get("Retry-After", 2))
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    raise GrampsError(f"Auth failed: {resp.status_code} {resp.text[:200]}")
                break
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

    async def _paged(self, path: str, page_size: int = 200, **params) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            resp = await self._request(
                "GET", path, params={"pagesize": page_size, "page": page, **params}
            )
            batch = resp.json()
            if not isinstance(batch, list) or not batch:
                break
            items.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return items

    # --- endpoints (grown as modules need them) ---

    async def get_metadata(self) -> dict:
        """Tree/server info; cheapest authenticated call — used by doctor."""
        resp = await self._request("GET", "/metadata/")
        return resp.json()

    async def list_people(self, extend_media: bool = False) -> list[dict]:
        params = {"extend": "media_list"} if extend_media else {}
        return await self._paged("/people/", **params)

    async def get_person(self, handle: str) -> dict:
        resp = await self._request("GET", f"/people/{handle}")
        return resp.json()

    async def update_person(self, handle: str, person_obj: dict) -> dict:
        resp = await self._request(
            "PUT", f"/people/{handle}",
            json=person_obj, headers={"Content-Type": "application/json"},
        )
        return resp.json()

    async def list_media(self) -> list[dict]:
        return await self._paged("/media/")

    async def get_place(self, handle: str) -> dict:
        resp = await self._request("GET", f"/places/{handle}")
        return resp.json()

    async def list_places(self, keys: str = "handle") -> list[dict]:
        return await self._paged("/places/", page_size=500, keys=keys)


def person_display_name(person: dict) -> str:
    """Extract display name from a Gramps person object."""
    name = person.get("primary_name")
    if not name:
        return "(unknown)"
    first = name.get("first_name", "")
    surnames = name.get("surname_list", [])
    surname = surnames[0].get("surname", "") if surnames else ""
    return f"{first} {surname}".strip() or "(unknown)"
