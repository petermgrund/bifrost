"""Slim Immich client — just what the single-asset Gramps sync needs.

Written against the Immich v3.0.x API. The per-asset key-value metadata
endpoints are Stable in v3; the sync reads gda.date / gda.gramps from them
and writes gramps_id/synced_at back after a successful sync (urd owns the
richer client, /opt/stacks/urd/urd/immich.py).
"""

from __future__ import annotations

import re

import httpx

_UUID_RE = re.compile(
    r"\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)


class ImmichError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Immich {status}: {message}")
        self.status = status
        self.message = message


def _checked_id(value: str) -> str:
    # Ids reach URL paths; without this a crafted id could steer the
    # API-key-bearing request to an arbitrary Immich endpoint.
    if not _UUID_RE.match(value or ""):
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

    async def get_asset(self, asset_id: str) -> dict:
        return (await self._request("GET", f"/assets/{_checked_id(asset_id)}")).json()

    async def get_faces(self, asset_id: str) -> list[dict]:
        return (await self._request("GET", "/faces", params={"id": _checked_id(asset_id)})).json()

    async def get_metadata(self, asset_id: str) -> dict:
        """The asset's key-value metadata as {key: value}."""
        items = (await self._request("GET", f"/assets/{_checked_id(asset_id)}/metadata")).json()
        return {item["key"]: item["value"] for item in items}

    async def put_metadata(self, asset_id: str, key: str, value: dict) -> None:
        await self._request(
            "PUT",
            f"/assets/{_checked_id(asset_id)}/metadata",
            json={"items": [{"key": key, "value": value}]},
        )
