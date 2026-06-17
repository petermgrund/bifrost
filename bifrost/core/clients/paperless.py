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
            follow_redirects=True,  # match requests' default (see GrampsClient)
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
            params = None  # baked into the 'next' URL
        return results

    async def resolve_tag_id(self, name: str) -> int | None:
        resp = await self._request("GET", "/api/tags/", params={"name__iexact": name})
        results = resp.json().get("results", [])
        return results[0]["id"] if results else None

    async def list_documents_by_tags(self, tag_ids: list[int]) -> list[dict]:
        """All docs carrying any of the given tags."""
        if not tag_ids:
            return []
        return await self._paginated(
            "/api/documents/",
            params={"tags__id__in": ",".join(str(t) for t in tag_ids)},
        )

    async def list_documents_by_tag(self, tag_id: int) -> list[dict]:
        return await self._paginated("/api/documents/", params={"tags__id": tag_id})

    async def get_document_metadata(self, doc_id: int) -> dict:
        """Checksums + on-disk filename (which may differ from the upload name)."""
        resp = await self._request("GET", f"/api/documents/{doc_id}/metadata/")
        return resp.json()

    async def resolve_custom_field_options(self, field_id: int) -> dict[str, str]:
        """{option_id: label} for a select custom field. Paperless stores the
        option's stable id, not the label, so we resolve once at startup."""
        resp = await self._request("GET", f"/api/custom_fields/{field_id}/")
        opts = resp.json().get("extra_data", {}).get("select_options") or []
        return {o["id"]: o["label"] for o in opts if "id" in o and "label" in o}

    @staticmethod
    def get_custom_field_value(doc: dict, field_id: int) -> str | None:
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
        """The document's ORIGINAL file bytes + content-type (the selected
        version's file under 3.0 versioning). `original=true` skips the
        archive PDF so OCR sees what the user actually uploaded."""
        resp = await self._request(
            "GET", f"/api/documents/{doc_id}/download/", params={"original": "true"})
        mime = resp.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
        return resp.content, mime

    async def patch_content(self, doc_id: int, content: str) -> None:
        """Overwrite the document's searchable text (content) field in place."""
        await self._request(
            "PATCH", f"/api/documents/{doc_id}/", json={"content": content})

    async def patch_tags(self, doc_id: int, tag_ids: list[int]) -> None:
        """Set the document's full tag list (pass existing + new to add one)."""
        await self._request(
            "PATCH", f"/api/documents/{doc_id}/", json={"tags": tag_ids})

    async def patch_fields(self, doc_id: int, payload: dict) -> None:
        """Generic document PATCH — title / created / correspondent /
        document_type / tags / custom_fields in one call (upload wizard save)."""
        await self._request("PATCH", f"/api/documents/{doc_id}/", json=payload)

    # --- ingest (upload wizard) ---

    async def upload(
        self, filename: str, data: bytes, mime: str, tags: list[int],
        title: str | None = None, created: str | None = None,
    ) -> str:
        """POST a file into the Paperless consume pipeline. Returns the consume
        TASK uuid (a string) — the document id does not exist until consumption
        finishes; poll get_task(uuid) for status + related_document."""
        form: list[tuple[str, str]] = [("tags", str(t)) for t in tags]
        if title:
            form.append(("title", title))
        if created:
            form.append(("created", created))
        resp = await self._request(
            "POST", "/api/documents/post_document/",
            files={"document": (filename, data, mime or "application/octet-stream")},
            data=form,
        )
        # Body is the task uuid as a bare JSON string.
        return str(resp.json()).strip()

    async def get_task(self, task_uuid: str) -> dict:
        """Status of a consume task: status (PENDING/STARTED/SUCCESS/FAILURE),
        related_document (the new doc id on success)."""
        resp = await self._request("GET", "/api/tasks/", params={"task_id": task_uuid})
        data = resp.json()
        items = data.get("results", []) if isinstance(data, dict) else data
        return items[0] if items else {}

    # --- option lists for the upload form (id + name) ---

    async def list_correspondents(self) -> list[dict]:
        return [{"id": c["id"], "name": c.get("name", "")}
                for c in await self._paginated("/api/correspondents/")]

    async def list_document_types(self) -> list[dict]:
        return [{"id": d["id"], "name": d.get("name", "")}
                for d in await self._paginated("/api/document_types/")]

    async def list_tags(self) -> list[dict]:
        return [{"id": t["id"], "name": t.get("name", "")}
                for t in await self._paginated("/api/tags/")]

    async def list_all_documents(self, fields: str | None = None) -> list[dict]:
        """Every document (paginated). `fields` trims the payload via the
        Paperless `fields=` selector when given."""
        params = {"fields": fields} if fields else None
        return await self._paginated("/api/documents/", params=params)
