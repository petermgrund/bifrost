"""Minimal Google Gemini (Generative Language API) client for document OCR.

Plain httpx, one capability: send a document image/PDF + a prompt, get text
back. Used to transcribe genealogy records (handwriting, old print, photos)
far better than Tesseract, writing the result into Paperless's content field.
"""

from __future__ import annotations

import base64

import httpx

API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    pass


class GeminiClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._key = api_key
        self._model = model
        self._client = httpx.AsyncClient(
            timeout=300.0, headers={"content-type": "application/json"})

    @property
    def configured(self) -> bool:
        return bool(self._key)

    async def close(self) -> None:
        await self._client.aclose()

    async def list_models(self) -> list[str]:
        """Model ids available to this key (for confirming the configured id)."""
        resp = await self._client.get(f"{API_BASE}/models", params={"key": self._key})
        if resp.status_code >= 400:
            raise GeminiError(f"{resp.status_code}: {resp.text[:300]}")
        return [m.get("name", "").removeprefix("models/")
                for m in resp.json().get("models", [])]

    async def transcribe(
        self, data: bytes, mime: str, prompt: str,
        thinking_budget: int | None = None,
    ) -> str:
        """Transcribe a document file (image or PDF) to plain text."""
        body: dict = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime,
                                "data": base64.b64encode(data).decode()}},
            ]}],
        }
        if thinking_budget is not None:
            body["generationConfig"] = {"thinkingConfig": {"thinkingBudget": thinking_budget}}
        resp = await self._client.post(
            f"{API_BASE}/models/{self._model}:generateContent",
            params={"key": self._key}, json=body)
        if resp.status_code >= 400:
            raise GeminiError(f"{resp.status_code}: {resp.text[:400]}")
        payload = resp.json()
        cands = payload.get("candidates") or []
        if not cands:
            fb = payload.get("promptFeedback") or {}
            raise GeminiError(f"no candidates returned ({fb or 'empty response'})")
        parts = ((cands[0].get("content") or {}).get("parts") or [])
        return "".join(p.get("text", "") for p in parts).strip()
