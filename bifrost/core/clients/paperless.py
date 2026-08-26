"""Paperless-ngx API client"""

from __future__ import annotations

import httpx


class PaperlessError(Exception):
    """Wraps non-2xx response from Paperless"""


class PaperlessClient:
    def __init__(self, base_url: str, api_token: str) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
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

    # --- endpoints ---

    async def count_tags(self) -> int:
        """auth call used by doctor"""
        resp = await self._request("GET", "/api/tags/", params={"page_size": 1})
        return int(resp.json().get("count", 0))

    async def version(self) -> str:
        resp = await self._request("GET", "/api/tags/", params={"page_size": 1})
        return resp.headers.get("x-version", "")

    async def _paginated(self, path: str, params: dict | None = None) -> list[dict]:
        results: list[dict] = []
        url: str | None = f"{self._base}{path}"
        while url:
            resp = await self._client.get(url, params=params)
            if resp.status_code >= 400:
                raise PaperlessError(f"GET {url} → {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            results.extend(data.get("results", []))
            url = data.get("next")
            params = None  # baked into next URL
        return results

    async def resolve_tag_id(self, name: str) -> int | None:
        resp = await self._request("GET", "/api/tags/", params={"name__iexact": name})
        results = resp.json().get("results", [])
        return results[0]["id"] if results else None

    async def list_documents_by_tags(self, tag_ids: list[int]) -> list[dict]:
        """All docs carrying any  given tags"""
        if not tag_ids:
            return []
        return await self._paginated(
            "/api/documents/",
            params={"tags__id__in": ",".join(str(t) for t in tag_ids)},
        )

    async def list_documents_by_tag(self, tag_id: int) -> list[dict]:
        return await self._paginated("/api/documents/", params={"tags__id": tag_id})

    async def get_document_metadata(self, doc_id: int) -> dict:
        """Checksums and on-disk filename"""
        resp = await self._request("GET", f"/api/documents/{doc_id}/metadata/")
        return resp.json()

    async def resolve_custom_field_options(self, field_id: int) -> dict[str, str]:
        """{option_id: label} for a select custom field"""
        resp = await self._request("GET", f"/api/custom_fields/{field_id}/")
        opts = resp.json().get("extra_data", {}).get("select_options") or []
        return {o["id"]: o["label"] for o in opts if "id" in o and "label" in o}

    @staticmethod
    def custom_field_value(doc: dict, field_id: int) -> str | None:
        for cf in doc.get("custom_fields", []):
            if cf["field"] == field_id:
                val = cf.get("value")
                if val is None or (isinstance(val, str) and not val.strip()):
                    return None
                return val
        return None

    async def patch_custom_fields(self, doc_id: int, custom_fields: list[dict]) -> None:
        await self._request(
            "PATCH", f"/api/documents/{doc_id}/",
            json={"custom_fields": custom_fields},
        )

    async def get_document(self, doc_id: int) -> dict:
        resp = await self._request("GET", f"/api/documents/{doc_id}/")
        return resp.json()

    async def download_original(self, doc_id: int) -> tuple[bytes, str]:
        """The document's original file bytes and content-type. `original=true` skips the
        archive PDF so OCR sees what the user actually uploaded"""
        resp = await self._request(
            "GET", f"/api/documents/{doc_id}/download/", params={"original": "true"})
        mime = resp.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
        return resp.content, mime

    async def patch_content(self, doc_id: int, content: str) -> None:
        """Overwrite doc searchable text field in place"""
        await self._request(
            "PATCH", f"/api/documents/{doc_id}/", json={"content": content})

    async def patch_tags(self, doc_id: int, tag_ids: list[int]) -> None:
        """Set the document's full tag list"""
        await self._request(
            "PATCH", f"/api/documents/{doc_id}/", json={"tags": tag_ids})

    async def update_version(
        self, doc_id: int, data: bytes, filename: str,
        version_label: str | None = None, mime: str = "application/pdf",
    ) -> str:
        """ bytes as a new version of  existing """
        resp = await self._request(
            "POST", f"/api/documents/{doc_id}/update_version/",
            files={"document": (filename, data, mime)},
            data={"version_label": version_label} if version_label else None,
            timeout=300.0,
        )
        try:
            return str(resp.json()).strip()
        except ValueError:
            return resp.text.strip().strip('"')

    async def task_status(self, task_uuid: str) -> dict | None:
        """task row from /api/tasks/"""
        resp = await self._request("GET", "/api/tasks/", params={"task_id": task_uuid})
        payload = resp.json()
        results = payload.get("results", []) if isinstance(payload, dict) else payload
        return results[0] if results else None

    async def list_documents(self, fields: str | None = None) -> list[dict]:
        """Every doc paginated"""
        params = {"fields": fields} if fields else None
        return await self._paginated("/api/documents/", params=params)
