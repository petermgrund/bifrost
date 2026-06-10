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
