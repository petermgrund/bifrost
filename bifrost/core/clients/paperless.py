"""Async Paperless-ngx API client (Token auth)."""

from __future__ import annotations

import httpx


class PaperlessError(Exception):
    """Wraps any non-2xx response from Paperless."""


class PaperlessClient:
    def __init__(self, base_url: str, api_token: str) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Token {api_token}",
                "Accept": "application/json; version=9",
            },
        )

    async def __aenter__(self) -> "PaperlessClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = await self._client.request(method, f"{self._base}{path}", **kwargs)
        if resp.status_code >= 400:
            raise PaperlessError(f"{method} {path} → {resp.status_code}: {resp.text[:500]}")
        return resp

    # --- endpoints (grown as modules need them) ---

    async def count_tags(self) -> int:
        """Cheap authenticated call — used by doctor."""
        resp = await self._request("GET", "/api/tags/", params={"page_size": 1})
        return int(resp.json().get("count", 0))
