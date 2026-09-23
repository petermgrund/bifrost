import asyncio
import copy
import logging

import pytest

from bifrost.core.clients.anthropic import AnthropicClient, AnthropicError

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

REJECTION_TEXT = (
    '{"type":"error","error":{"type":"invalid_request_error","message":'
    '"claude-example-1 forces tool use is not compatible with this model"}}'
)


class _Resp:
    def __init__(self, status_code, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_forced_tool_use_rejection_falls_back_to_auto():
    client = AnthropicClient("key", "claude-example-1")
    calls = []

    async def fake_post(url, json=None):
        calls.append(copy.deepcopy(json))
        if len(calls) == 1:
            return _Resp(400, text=REJECTION_TEXT)
        return _Resp(200, payload={
            "content": [{"type": "tool_use", "input": {"ok": True}}]})

    client._client.post = fake_post
    result = asyncio.run(client.complete_structured("sys", "user", SCHEMA))
    asyncio.run(client.close())

    assert result == {"ok": True}
    assert len(calls) == 2
    assert calls[0]["tool_choice"] == {"type": "tool", "name": "emit_result"}
    assert calls[1]["tool_choice"] == {"type": "auto"}
    assert calls[1]["messages"][0]["content"].endswith(
        "Respond ONLY by calling the emit_result tool.")



def test_structured_call_caches_the_system_block_for_an_hour(caplog):
    client = AnthropicClient("key", "m")
    calls = []

    async def fake_post(url, json=None):
        calls.append(copy.deepcopy(json))
        return _Resp(200, payload={
            "content": [{"type": "tool_use", "input": {"ok": True}}],
            "usage": {"input_tokens": 3, "cache_read_input_tokens": 70000}})

    client._client.post = fake_post
    with caplog.at_level(logging.INFO, logger="bifrost.anthropic"):
        asyncio.run(client.complete_structured("sys", "user", SCHEMA))
    asyncio.run(client.close())
    assert calls[0]["system"] == [{"type": "text", "text": "sys",
                                   "cache_control": {"type": "ephemeral", "ttl": "1h"}}]
    assert "cache_read=70000" in caplog.text


def _one_call(payload):
    client = AnthropicClient("key", "m")
    calls = []

    async def fake_post(url, json=None):
        calls.append(copy.deepcopy(json))
        return _Resp(200, payload=payload)

    client._client.post = fake_post
    try:
        return calls, asyncio.run(client.complete_structured("sys", "user", SCHEMA, max_tokens=50))
    finally:
        asyncio.run(client.close())


def test_structured_tool_is_strict():
    calls, _ = _one_call({"content": [{"type": "tool_use", "input": {"ok": True}}]})
    assert calls[0]["tools"][0]["strict"] is True


@pytest.mark.parametrize("stop_reason, message", [
    ("max_tokens", "cut off at max_tokens=50"),
    ("refusal", "declined"),
])
def test_cut_off_or_declined_reply_is_an_error_not_a_partial_result(stop_reason, message):
    with pytest.raises(AnthropicError, match=message):
        _one_call({"stop_reason": stop_reason,
                   "content": [{"type": "tool_use", "input": {"ok": "partial"}}]})
