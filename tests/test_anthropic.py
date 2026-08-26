import asyncio
import copy

from bifrost.core.clients.anthropic import AnthropicClient

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
