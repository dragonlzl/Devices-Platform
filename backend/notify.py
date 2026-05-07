import os
import re
from typing import Any, Dict, List, Optional

import httpx


class NotifyError(RuntimeError):
    pass


PORTAL_NOTIFICATION_TEMPLATE_ID = "AAqepmbB3M23t"
PORTAL_NOTIFICATION_TEMPLATE_VERSION = "1.0.4"
DEFAULT_PORTAL_NOTIFICATION_SEND_URL = "http://192.168.50.10:8756/api/notifications/send"
DEFAULT_BORROW_ADMIN_URL = "http://192.168.50.10:8090/admin"
DEFAULT_FEISHU_CARD_COLOR = "blue"


class PortalNotificationError(NotifyError):
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        code: str = "PORTAL_NOTIFICATION_FAILED",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def build_text_message(title: str, body: str) -> str:
    return f"{title}\n{body}"


def _split_field_line(line: str) -> Optional[tuple[str, str]]:
    match = re.match(r"^([^:：]+)[:：]\s*(.*)$", line)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip() or "-"


def _feishu_card_fields(body: str) -> List[Dict[str, Any]]:
    fields = []
    for line in str(body or "").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        parsed = _split_field_line(cleaned)
        if parsed:
            label, value = parsed
            content = f"**{label}:** {value}"
        else:
            content = cleaned
        fields.append({"is_short": False, "text": {"tag": "lark_md", "content": content}})
    return fields


def build_feishu_card_payload(
    title: str,
    body: str,
    *,
    card_color: str = DEFAULT_FEISHU_CARD_COLOR,
    admin_url: str = DEFAULT_BORROW_ADMIN_URL,
) -> Dict[str, Any]:
    fields = _feishu_card_fields(body)
    admin_link = str(admin_url or DEFAULT_BORROW_ADMIN_URL).strip() or DEFAULT_BORROW_ADMIN_URL
    fields.append(
        {
            "is_short": False,
            "text": {"tag": "lark_md", "content": f"**设备借用管理页:** [点击查看]({admin_link})"},
        }
    )
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": str(card_color or DEFAULT_FEISHU_CARD_COLOR).strip() or DEFAULT_FEISHU_CARD_COLOR,
                "title": {"tag": "plain_text", "content": str(title or "设备借用通知").strip() or "设备借用通知"},
            },
            "elements": [{"tag": "div", "fields": fields}],
        },
    }


async def send_feishu_message(
    client: httpx.AsyncClient,
    webhook: str,
    title: str,
    body: str,
    *,
    card_color: str = DEFAULT_FEISHU_CARD_COLOR,
    admin_url: str = DEFAULT_BORROW_ADMIN_URL,
) -> None:
    payload = build_feishu_card_payload(title, body, card_color=card_color, admin_url=admin_url)
    response = await client.post(webhook, json=payload)
    if response.status_code >= 300:
        raise NotifyError(f"飞书通知失败: {response.status_code} {response.text}")


def _portal_notification_url() -> str:
    return os.environ.get("PORTAL_NOTIFICATION_SEND_URL", DEFAULT_PORTAL_NOTIFICATION_SEND_URL).strip()


def _clean_portal_error_message(value: Any) -> str:
    message = str(value or "").strip()
    message = message.replace("\n", " ")
    import re

    message = re.sub(r"Bearer\s+[^\s,;]+", "Bearer <redacted>", message, flags=re.IGNORECASE)
    message = re.sub(r"(Authorization\s*[:=]\s*)[^\s,;]+", r"\1<redacted>", message, flags=re.IGNORECASE)
    message = re.sub(r"(Cookie\s*[:=]\s*)[^,;]+", r"\1<redacted>", message, flags=re.IGNORECASE)
    message = re.sub(r"(portal_jwt\s*[:=]\s*)[^\s,;]+", r"\1<redacted>", message, flags=re.IGNORECASE)
    message = re.sub(r"(service_token\s*[:=]\s*)[^\s,;]+", r"\1<redacted>", message, flags=re.IGNORECASE)
    return message[:300] if message else "门户通知发送失败"


def _ensure_object(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise PortalNotificationError(
            f"{label}必须是 JSON object",
            status_code=400,
            code="NOTIFICATION_REQUEST_INVALID",
        )
    return value


def build_portal_notification_body(
    *,
    recipient_user_id: str,
    payload: Dict[str, Any],
    template_variable: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not str(recipient_user_id or "").strip():
        raise PortalNotificationError(
            "recipient_user_id不能为空",
            status_code=400,
            code="NOTIFICATION_REQUEST_INVALID",
        )
    return {
        "recipient_user_id": str(recipient_user_id).strip(),
        "template_id": PORTAL_NOTIFICATION_TEMPLATE_ID,
        "template_version_name": PORTAL_NOTIFICATION_TEMPLATE_VERSION,
        "payload": _ensure_object(payload, "payload"),
        "template_variable": _ensure_object(template_variable or {}, "template_variable"),
    }


async def send_portal_notification(
    client: httpx.AsyncClient,
    *,
    recipient_user_id: str,
    payload: Dict[str, Any],
    portal_jwt: Optional[str] = None,
    cookie: Optional[str] = None,
    service_id: Optional[str] = None,
    service_token: Optional[str] = None,
    template_variable: Optional[Dict[str, Any]] = None,
    send_url: Optional[str] = None,
) -> Dict[str, Any]:
    jwt = str(portal_jwt or "").strip()
    cookie_value = str(cookie or "").strip()
    service_id_value = str(service_id or "").strip()
    service_token_value = str(service_token or "").strip()
    if not jwt and not cookie_value and not service_token_value:
        raise PortalNotificationError(
            "缺少门户通知鉴权凭证",
            status_code=401,
            code="NOTIFICATION_AUTH_REQUIRED",
        )

    headers = {"Content-Type": "application/json"}
    if service_token_value:
        if not service_id_value:
            raise PortalNotificationError(
                "缺少门户通知服务 ID",
                status_code=401,
                code="NOTIFICATION_AUTH_REQUIRED",
            )
        headers["X-Portal-Service-Id"] = service_id_value
        headers["Authorization"] = f"Bearer {service_token_value}"
    elif jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    else:
        headers["Cookie"] = cookie_value

    body = build_portal_notification_body(
        recipient_user_id=recipient_user_id,
        payload=payload,
        template_variable=template_variable,
    )
    try:
        response = await client.post(send_url or _portal_notification_url(), headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise PortalNotificationError(
            "门户通知请求失败",
            code=exc.__class__.__name__ or "PORTAL_NOTIFICATION_HTTP_ERROR",
        ) from exc

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {}

    code = str(response_payload.get("code") or f"HTTP_{response.status_code}")
    message = _clean_portal_error_message(response_payload.get("message") or response.reason_phrase or "门户通知发送失败")
    if response.status_code >= 400:
        raise PortalNotificationError(message, status_code=response.status_code, code=code)
    if response_payload.get("success") is False:
        raise PortalNotificationError(message, status_code=response.status_code, code=code)
    return response_payload
