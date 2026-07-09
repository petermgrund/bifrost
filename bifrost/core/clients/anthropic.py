import annotations

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

    async def complete_text(self, system: str, user: str, max_tokens: int = 1000) -> str:
        """One-shot plain-text completion."""
        resp = await self._client.post(API_URL, json={
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
        """One-shot structured completion via the emit_result tool.

        Forced tool choice where the model supports it; some models (e.g.
        claude-fable-5) reject forcing, so fall back to auto + an explicit
        instruction and validate that the tool actually got called."""
        body = {
            "model": self._model,
            "max_tokens": max_tokens,
            # Cache the system prefix: it carries the full house-style guide
            # (~50k tokens, identical across calls), so this turns most of the
            # input cost into cheap cache reads within the 5-min window.
            "system": [{"type": "text", "text": system,
                        "cache_control": {"type": "ephemeral"}}],
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
