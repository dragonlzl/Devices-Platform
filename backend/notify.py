from typing import Optional

import httpx


class NotifyError(RuntimeError):
    pass


def build_text_message(title: str, body: str) -> str:
    return f"{title}\n{body}"


async def send_feishu_message(client: httpx.AsyncClient, webhook: str, title: str, body: str) -> None:
    payload = {
        "msg_type": "text",
        "content": {"text": build_text_message(title, body)},
    }
    response = await client.post(webhook, json=payload)
    if response.status_code >= 300:
        raise NotifyError(f"飞书通知失败: {response.status_code} {response.text}")
