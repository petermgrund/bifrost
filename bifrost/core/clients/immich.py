"""The single adapter for every Immich API call Bifrost makes.

All HTTP against Immich lives here so an upstream API change (Immich majors
break third-party consumers roughly annually; v2→v3 did) is a one-file fix.
Written against the v3.0.x OpenAPI spec. The per-asset key-value metadata
endpoints are Stable in v3 (the bulk /assets/metadata endpoint is Beta, so
bulk writes fan out over the per-asset route instead); the gda.* values they
carry are the core/gda contract.

Every caller-supplied id that reaches a URL path is validated as a UUID
first — otherwise a crafted id could redirect the server's API-key-bearing
request to an arbitrary Immich endpoint.
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote

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

    # -- server ------------------------------------------------------------

    async def server_version(self) -> dict:
        return (await self._request("GET", "/server/version")).json()

    async def get_me(self) -> dict:
        return (await self._request("GET", "/users/me")).json()

    # -- assets ------------------------------------------------------------

    async def search_assets(
        self,
        page: int = 1,
        size: int = 60,
        album_id: str | None = None,
        person_id: str | None = None,
        filename: str | None = None,
        order: str = "desc",
    ) -> dict:
        body: dict = {
            "page": page, "size": size, "order": order,
            "withStacked": True, "withExif": True,
        }
        if album_id:
            body["albumIds"] = [_checked_id(album_id)]
        if person_id:
            body["personIds"] = [_checked_id(person_id)]
        if filename:
            body["originalFileName"] = filename
        data = (await self._request("POST", "/search/metadata", json=body)).json()
        assets = data.get("assets") or {}
        # v3.0.1 returns nextPage as the STRING '2'; feeding that back into
        # the body fails Immich's numeric validation, which silently capped
        # every paged fan-out at one page — normalize to int here, loudly.
        next_page = assets.get("nextPage")
        return {
            "items": assets.get("items") or [],
            "nextPage": int(next_page) if next_page is not None else None,
        }

    async def get_asset(self, asset_id: str) -> dict:
        return (await self._request("GET", f"/assets/{_checked_id(asset_id)}")).json()

    async def get_faces(self, asset_id: str) -> list[dict]:
        return (await self._request("GET", "/faces", params={"id": _checked_id(asset_id)})).json()

    async def thumbnail(self, asset_id: str, size: str = "thumbnail") -> tuple[bytes, str]:
        resp = await self._request(
            "GET", f"/assets/{_checked_id(asset_id)}/thumbnail", params={"size": size}
        )
        return resp.content, resp.headers.get("content-type", "image/jpeg")

    # -- per-asset key-value metadata (Stable in v3) -------------------------

    async def get_metadata(self, asset_id: str) -> dict:
        """Return the asset's KV metadata as {key: value}."""
        items = (await self._request("GET", f"/assets/{_checked_id(asset_id)}/metadata")).json()
        return {item["key"]: item["value"] for item in items}

    async def put_metadata(self, asset_id: str, key: str, value: dict) -> None:
        await self._request(
            "PUT",
            f"/assets/{_checked_id(asset_id)}/metadata",
            json={"items": [{"key": key, "value": value}]},
        )

    async def delete_metadata(self, asset_id: str, key: str) -> None:
        path = f"/assets/{_checked_id(asset_id)}/metadata/{quote(key, safe='')}"
        try:
            await self._request("DELETE", path)
        except ImmichError as exc:
            if exc.status != 404:  # deleting an absent key is fine
                raise

    async def get_metadata_many(self, asset_ids: list[str], concurrency: int = 8) -> dict:
        """Fetch KV metadata for many assets -> {asset_id: {key: value} | None}.

        None marks a FAILED fetch — callers must not render that as "no
        metadata", or a transient Immich error would invite the user to
        overwrite existing values.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def one(asset_id: str) -> tuple[str, dict | None]:
            async with semaphore:
                try:
                    return asset_id, await self.get_metadata(asset_id)
                except ImmichError as exc:
                    log.warning("KV metadata fetch failed for asset %s: %s", asset_id, exc)
                    return asset_id, None

        return dict(await asyncio.gather(*(one(a) for a in asset_ids)))

    # -- browse helpers ------------------------------------------------------

    async def albums(self) -> list[dict]:
        return (await self._request("GET", "/albums")).json()

    async def people(self) -> list[dict]:
        people: list[dict] = []
        page = 1
        while True:
            data = (
                await self._request(
                    "GET", "/people", params={"page": page, "size": 500, "withHidden": False}
                )
            ).json()
            batch = data.get("people") if isinstance(data, dict) else data
            people.extend(batch or [])
            if not isinstance(data, dict) or not data.get("hasNextPage"):
                break
            page += 1
        return people

    async def get_stack(self, stack_id: str) -> dict:
        return (await self._request("GET", f"/stacks/{_checked_id(stack_id)}")).json()

    async def list_stacks(self) -> list[dict]:
        """Every stack: {id, primaryAssetId, assets: [...]}. The only complete
        source of stack membership — v3.0.1 search results report stack: null
        even for primaries (verified live), so listings must consult this."""
        return (await self._request("GET", "/stacks")).json()

    async def update_stack_primary(self, stack_id: str, asset_id: str) -> dict:
        """Make asset_id the stack's primary (PUT /stacks/{id}, verified on
        v3.0.1). The primary is the cover Immich itself shows."""
        return (
            await self._request(
                "PUT", f"/stacks/{_checked_id(stack_id)}",
                json={"primaryAssetId": _checked_id(asset_id)},
            )
        ).json()

    async def create_stack(self, asset_ids: list[str]) -> dict:
        """Stack the given assets. The FIRST id becomes the primary, and any
        asset already in a stack brings its whole stack along into the new
        one (merge — verified on v3.0.1)."""
        return (
            await self._request(
                "POST", "/stacks",
                json={"assetIds": [_checked_id(a) for a in asset_ids]},
            )
        ).json()

    async def remove_stack_asset(self, stack_id: str, asset_id: str) -> None:
        await self._request(
            "DELETE", f"/stacks/{_checked_id(stack_id)}/assets/{_checked_id(asset_id)}"
        )

    async def delete_stack(self, stack_id: str) -> None:
        """Dissolve a stack; its assets stay, loose (verified on v3.0.1)."""
        await self._request("DELETE", f"/stacks/{_checked_id(stack_id)}")
