"""Gramps Web API client"""

from __future__ import annotations

import asyncio
import json
import re

import httpx


class GrampsError(Exception):
    """Wraps non-2xx response from Gramps Web"""


class GrampsClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base = base_url.rstrip("/")
        self._user = username
        self._pass = password
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
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
                raise GrampsError(f"No token in auth response {data}")
            self._token = token

    async def _request(
        self, method: str, path: str, ok_404: bool = False, **kwargs
    ) -> httpx.Response:
        await self._ensure_token()
        headers = kwargs.pop("headers", {}) or {}
        headers["Authorization"] = f"Bearer {self._token}"
        resp = await self._client.request(
            method, f"{self._base}{path}", headers=headers, **kwargs
        )
        if resp.status_code == 401:
            #token expired
            self._token = None
            await self._ensure_token()
            headers["Authorization"] = f"Bearer {self._token}"
            resp = await self._client.request(
                method, f"{self._base}{path}", headers=headers, **kwargs
            )
        if resp.status_code == 404 and ok_404:
            return resp
        if resp.status_code >= 400:
            raise GrampsError(f"{method} {path} → {resp.status_code}: {resp.text[:500]}")
        return resp

    async def page_of(self, path: str, page: int, page_size: int = 200,
                      **params) -> tuple[list[dict], int]:
        """One page of a listing plus the total count"""
        resp = await self._request(
            "GET", path, params={"pagesize": page_size, "page": page, **params})
        items = resp.json()
        items = items if isinstance(items, list) else []
        return items, int(resp.headers.get("X-Total-Count") or len(items))

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

    # --- endpoints ---

    async def get_metadata(self) -> dict:
        """Tree/server info"""
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

    async def recent_media(self, limit: int = 30) -> list[dict]:
        """Media objects most recently changed in Gramps"""
        resp = await self._request(
            "GET", "/media/",
            params={"sort": "-change", "pagesize": limit, "page": 1,
                    "keys": "handle,gramps_id,desc,attribute_list,change"})
        items = resp.json()
        return items if isinstance(items, list) else []

    async def bookmarks(self) -> dict:
        resp = await self._request("GET", "/bookmarks/")
        data = resp.json()
        return data if isinstance(data, dict) else {}

    async def search_media(self, query: str, limit: int = 10) -> list[dict]:
        """Media whose title or Gramps ID matches the query, via Gramps filter rules"""
        pattern = re.escape(query.strip())
        rules = {"function": "or", "rules": [
            {"name": "HasMedia", "values": [pattern, "", "", ""], "regex": True},
            {"name": "RegExpIdOf", "values": [pattern]}]}
        resp = await self._request(
            "GET", "/media/",
            params={"rules": json.dumps(rules), "pagesize": limit, "page": 1,
                    "keys": "handle,gramps_id,desc,attribute_list,change"})
        items = resp.json()
        return items if isinstance(items, list) else []

    async def count(self, path: str) -> int:
        """Total objects"""
        resp = await self._request("GET", path, params={"pagesize": 1, "page": 1})
        return int(resp.headers.get("X-Total-Count", 0))

    async def list_media_gramps_ids(self) -> set[str]:
        items = await self._paged("/media/", keys="gramps_id")
        return {m["gramps_id"] for m in items if m.get("gramps_id")}

    async def create_media(self, media_obj: dict) -> dict:
        resp = await self._request(
            "POST", "/objects",
            json=[media_obj], headers={"Content-Type": "application/json"},
        )
        return resp.json()

    async def update_media(self, handle: str, media_obj: dict) -> dict:
        resp = await self._request(
            "PUT", f"/media/{handle}",
            json=media_obj, headers={"Content-Type": "application/json"},
        )
        return resp.json()

    async def update_place(self, handle: str, place_obj: dict) -> dict:
        resp = await self._request(
            "PUT", f"/places/{handle}",
            json=place_obj, headers={"Content-Type": "application/json"},
        )
        return resp.json()

    async def list_places_full(self) -> list[dict]:
        return await self._paged("/places/")

    async def list_transaction_history(self, payloads: bool = False) -> list[dict]:
        """The tree's full transaction log"""
        params = {"old": 1, "new": 1} if payloads else {}
        return await self._paged("/transactions/history/", page_size=1000, **params)

    async def list_events_min(self) -> list[dict]:
        return await self._paged("/events/", keys="handle,citation_list")

    async def list_handles(self, path: str) -> set[str]:
        return {o["handle"] for o in await self._paged(path, page_size=1000, keys="handle")}

    async def get_media_by_gramps_id(self, gramps_id: str) -> dict | None:
        resp = await self._request(
            "GET", "/media/", ok_404=True, params={"gramps_id": gramps_id}
        )
        if resp.status_code == 404:
            return None
        items = resp.json()
        if items and isinstance(items, list):
            for m in items:
                if m.get("gramps_id") == gramps_id:
                    return m
        return None

    async def create_note(self, note_obj: dict) -> dict:
        return await self.create_object(note_obj)

    async def create_object(self, obj: dict) -> dict:
        """Create any Gramps object"""
        resp = await self._request(
            "POST", "/objects",
            json=[obj], headers={"Content-Type": "application/json"},
        )
        return resp.json()

    async def update_note(self, handle: str, note_obj: dict) -> dict:
        resp = await self._request(
            "PUT", f"/notes/{handle}",
            json=note_obj, headers={"Content-Type": "application/json"},
        )
        return resp.json()

    async def media_thumbnail(self, handle: str, size: int = 64) -> tuple[bytes, str]:
        resp = await self._request("GET", f"/media/{handle}/thumbnail/{size}")
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")

    async def get_media_backlinks(self, handle: str) -> dict:
        """Objects referencing a media object"""
        resp = await self._request(
            "GET", f"/media/{handle}", params={"backlinks": "true"}
        )
        return resp.json().get("backlinks", {})

    async def get_object(self, api_path: str, handle: str, **params) -> dict:
        resp = await self._request(
            "GET", f"/{api_path}/{handle}", params=params or None)
        return resp.json()

    async def update_object(self, api_path: str, handle: str, obj: dict) -> dict:
        resp = await self._request(
            "PUT", f"/{api_path}/{handle}",
            json=obj, headers={"Content-Type": "application/json"},
        )
        return resp.json()

    async def get_tag_handle(self, name: str) -> str | None:
        resp = await self._request("GET", "/tags/", params={"keys": "handle,name"})
        for t in resp.json() or []:
            if t.get("name") == name:
                return t.get("handle")
        return None

    async def get_place_by_gramps_id(self, gramps_id: str) -> dict | None:
        resp = await self._request(
            "GET", "/places/", ok_404=True, params={"gramps_id": gramps_id})
        if resp.status_code == 404:
            return None
        items = resp.json()
        if isinstance(items, list):
            for p in items:
                if p.get("gramps_id") == gramps_id:
                    return p
        return None

    async def get_place(self, handle: str) -> dict:
        resp = await self._request("GET", f"/places/{handle}")
        return resp.json()

    async def list_places(self, keys: str = "handle") -> list[dict]:
        return await self._paged("/places/", page_size=500, keys=keys)


def person_display_name(person: dict) -> str:
    """Extract display name from a Gramps person"""
    name = person.get("primary_name")
    if not name:
        return "(unknown)"
    first = name.get("first_name", "")
    surnames = name.get("surname_list", [])
    surname = surnames[0].get("surname", "") if surnames else ""
    return f"{first} {surname}".strip() or "(unknown)"
