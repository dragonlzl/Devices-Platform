import json
import sys
from pathlib import Path

import asyncio
import httpx
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.llm import DEFAULT_LLM_TIMEOUT, LLMError, _parse_device_ids, call_llm  # noqa: E402


class DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self):
        self.captured = {}

    async def post(self, url, headers=None, json=None, **kwargs):
        self.captured["url"] = url
        self.captured["headers"] = headers
        self.captured["json"] = json
        self.captured["timeout"] = kwargs.get("timeout")
        return DummyResponse(200, {"output_text": "{\"device_ids\": []}"})


def test_call_llm_responses_uses_input_text():
    client = DummyClient()

    async def run() -> None:
        config = {
            "api_type": "openai_responses",
            "api_key": "test-key",
            "model": "gpt-5.2",
            "max_tokens": 123,
            "base_url": "http://test/v1/responses",
        }
        result = await call_llm(client, config, "system", "user")
        assert result == {"device_ids": []}

    asyncio.run(run())
    assert client.captured["timeout"] == DEFAULT_LLM_TIMEOUT
    assert client.captured["json"]["stream"] is False
    assert client.captured["json"]["input"][0]["content"][0]["type"] == "input_text"
    assert client.captured["json"]["input"][1]["content"][0]["type"] == "input_text"


class TimeoutClient:
    async def post(self, url, headers=None, json=None, **kwargs):
        raise httpx.ReadTimeout("timeout")


def test_call_llm_handles_timeout():
    client = TimeoutClient()

    async def run() -> None:
        config = {
            "api_type": "openai_responses",
            "api_key": "test-key",
            "model": "gpt-5.2",
            "max_tokens": 123,
            "base_url": "http://test/v1/responses",
        }
        with pytest.raises(LLMError) as exc:
            await call_llm(client, config, "system", "user")
        assert "LLM 请求失败" in str(exc.value)

    asyncio.run(run())


def test_parse_device_ids_from_fence():
    text = """这里是结果:
```json
{"device_ids":[1,2],"reason":"ok"}
```
"""
    parsed = _parse_device_ids(text)
    assert parsed["device_ids"] == [1, 2]


def test_parse_device_ids_from_text():
    parsed = _parse_device_ids("device_ids: 3, 4, 5")
    assert parsed["device_ids"] == [3, 4, 5]
