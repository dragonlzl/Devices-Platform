import json
import re
from typing import Any, Dict, Optional

import httpx


DEFAULT_LLM_TIMEOUT = 300.0


class LLMError(RuntimeError):
    pass


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _build_url(base_url: str, api_type: str) -> str:
    base = _normalize_base_url(base_url)
    if api_type == "openai":
        if base.endswith("/chat/completions") or base.endswith("/v1/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"
    if api_type == "openai_responses":
        if base.endswith("/responses") or base.endswith("/v1/responses"):
            return base
        if base.endswith("/v1"):
            return f"{base}/responses"
        return f"{base}/v1/responses"
    raise LLMError("不支持的模型类型")


def _build_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _is_http_exception(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPError):
        return True
    return exc.__class__.__module__.startswith("httpcore")


def _extract_openai_text(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise LLMError("LLM 返回为空")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise LLMError("LLM 返回内容为空")
    return content


def _extract_responses_text(payload: Dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if output_text:
        return output_text
    outputs = payload.get("output") or []
    for item in outputs:
        content_list = item.get("content") or []
        for chunk in content_list:
            if chunk.get("type") == "output_text" and chunk.get("text"):
                return chunk.get("text")
    raise LLMError("LLM 返回内容为空")


def _parse_device_ids(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise LLMError("LLM 返回内容为空")
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        extracted = _extract_json_block(cleaned)
        if extracted is not None:
            try:
                parsed = json.loads(extracted)
            except json.JSONDecodeError as inner_exc:
                raise LLMError(f"解析 JSON 失败: {inner_exc}")
        else:
            device_ids = _extract_ids_from_text(cleaned)
            if device_ids:
                return {"device_ids": device_ids}
            raise LLMError(f"解析 JSON 失败: {exc}")
    if isinstance(parsed, dict) and "device_ids" in parsed:
        return parsed
    if isinstance(parsed, list):
        return {"device_ids": parsed}
    raise LLMError("JSON 格式不符合预期")


def _extract_json_block(text: str) -> Optional[str]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
    return None


def _extract_ids_from_text(text: str) -> Optional[list]:
    if "device_ids" not in text:
        return None
    match = re.search(r"device_ids[^\d\[]*(\[[^\]]*\]|\d+(?:\s*,\s*\d+)*)", text, re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1)
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            return [int(item) for item in parsed if isinstance(item, (int, float, str)) and str(item).isdigit()]
        return None
    ids = [int(item) for item in re.findall(r"\d+", raw)]
    return ids or None


async def call_llm(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    timeout_value = config.get("timeout")
    try:
        request_timeout = float(timeout_value) if timeout_value is not None else DEFAULT_LLM_TIMEOUT
    except (TypeError, ValueError):
        request_timeout = DEFAULT_LLM_TIMEOUT
    api_type = config["api_type"]
    api_key = config["api_key"]
    model = config["model"]
    max_tokens = config["max_tokens"]

    headers = _build_headers(api_key)

    if api_type == "openai":
        url = _build_url(config["base_url"], api_type)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=request_timeout)
        except Exception as exc:
            if _is_http_exception(exc):
                raise LLMError(f"LLM 请求失败: {exc}")
            raise
        if response.status_code >= 300:
            raise LLMError(f"LLM 请求失败: {response.status_code} {response.text}")
        content = _extract_openai_text(response.json())
        return _parse_device_ids(content)

    if api_type == "openai_responses":
        url = _build_url(config["base_url"], api_type)
        payload = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            "max_output_tokens": max_tokens,
            "stream": False,
            "temperature": 0.2,
        }
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=request_timeout)
        except Exception as exc:
            if _is_http_exception(exc):
                raise LLMError(f"LLM 请求失败: {exc}")
            raise
        if response.status_code >= 300:
            raise LLMError(f"LLM 请求失败: {response.status_code} {response.text}")
        content = _extract_responses_text(response.json())
        return _parse_device_ids(content)

    raise LLMError("不支持的模型类型")
