from __future__ import annotations

import logging

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

log = logging.getLogger("bifrost.anthropic")


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

    async def _post(self, body: dict) -> httpx.Response:
        resp = await self._client.post(API_URL, json=body)
        if resp.status_code < 400:
            u = resp.json().get("usage") or {}
            log.info("%s in=%s cache_read=%s cache_write=%s out=%s", body["model"],
                     u.get("input_tokens"), u.get("cache_read_input_tokens"),
                     u.get("cache_creation_input_tokens"), u.get("output_tokens"))
        return resp

    async def complete_text(self, system: str, user: str, max_tokens: int = 1000) -> str:
        """plain-text completion"""
        resp = await self._post({
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        })
        if resp.status_code >= 400:
            raise AnthropicError(f"{resp.status_code}: {resp.text[:500]}")
        return "".join(
            b.get("text", "") for b in resp.json().get("content", [])
            if b.get("type") == "text").strip()

    async def complete_structured(
        self, system: str, user: str, schema: dict, max_tokens: int = 4000
    ) -> dict:
        body = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system,
                        "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            "messages": [{"role": "user", "content": user}],
            "tools": [{
                "name": "emit_result",
                "description": "Emit the structured result.",
                "strict": True,  # the API enforces the schema, so nested objects arrive as objects
                "input_schema": schema,
            }],
            "tool_choice": {"type": "tool", "name": "emit_result"},
        }
        resp = await self._post(body)
        if resp.status_code == 400 and "forces tool use is not compatible" in resp.text:
            body["tool_choice"] = {"type": "auto"}
            body["messages"][0]["content"] += (
                "\n\nRespond ONLY by calling the emit_result tool.")
            resp = await self._post(body)
        if resp.status_code >= 400:
            raise AnthropicError(f"{resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        # the schema guarantee does not hold for a cut-off or declined reply
        if data.get("stop_reason") == "max_tokens":
            raise AnthropicError(f"output cut off at max_tokens={max_tokens}")
        if data.get("stop_reason") == "refusal":
            raise AnthropicError("the model declined this request")
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                return block["input"]
        raise AnthropicError("try again")
