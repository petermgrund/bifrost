"""Minimal Claude API client — structured completion via forced tool use.

Plain httpx, no SDK: bifrost needs exactly one capability (give me JSON
matching this schema) and one endpoint.
"""

from __future__ import annotations

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicError(Exception):
    pass


class AnthropicClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
        )

    @property
    def configured(self) -> bool:
        return bool(self._client.headers.get("x-api-key"))

    async def close(self) -> None:
        await self._client.aclose()

    async def complete_structured(
        self, system: str, user: str, schema: dict, max_tokens: int = 4000
    ) -> dict:
        """One-shot structured completion via the emit_result tool.

        Forced tool choice where the model supports it; some models (e.g.
        claude-fable-5) reject forcing, so fall back to auto + an explicit
        instruction and validate that the tool actually got called."""
        body = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [{
                "name": "emit_result",
                "description": "Emit the structured result. Always call this tool.",
                "input_schema": schema,
            }],
            "tool_choice": {"type": "tool", "name": "emit_result"},
        }
        resp = await self._client.post(API_URL, json=body)
        if resp.status_code == 400 and "forces tool use is not compatible" in resp.text:
            body["tool_choice"] = {"type": "auto"}
            body["messages"][0]["content"] += (
                "\n\nRespond ONLY by calling the emit_result tool.")
            resp = await self._client.post(API_URL, json=body)
        if resp.status_code >= 400:
            raise AnthropicError(f"{resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                return block["input"]
        raise AnthropicError("model answered without calling emit_result — try again")
