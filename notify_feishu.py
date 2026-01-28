#!/usr/bin/env python3
"""
飞书机器人通知脚本。
优先使用命令行参数或环境变量 FEISHU_WEBHOOK，若未提供则读取同目录下的
feishu_config.json（需包含 webhook 字段）。如有自定义根证书，可通过环境变量
FEISHU_CA_BUNDLE 指定证书路径。
"""

import json
import os
import sys
import ssl
import socket
import time
import urllib.error
import urllib.request
import subprocess


MESSAGE_TEXT = "任务执行完毕！！！"
CONFIG_FILENAME = "feishu_config.json"
FEATURE_LOG_FILENAME = "FEATURE_LOG.md"


def build_ssl_context() -> ssl.SSLContext:
    """
    构造 SSL Context。
    - 若设置 FEISHU_CA_BUNDLE，则使用指定证书路径。
    - 其次尝试使用 certifi 的 CA 包。
    - 最后回退到系统默认证书。
    """
    ca_bundle = os.environ.get("FEISHU_CA_BUNDLE")
    if ca_bundle:
        if not os.path.exists(ca_bundle):
            raise FileNotFoundError(f"FEISHU_CA_BUNDLE 指定的证书不存在: {ca_bundle}")
        return ssl.create_default_context(cafile=ca_bundle)

    try:
        import certifi
    except ImportError:
        certifi = None

    if certifi:
        return ssl.create_default_context(cafile=certifi.where())

    return ssl.create_default_context()


def load_webhook_from_config(config_path: str) -> str:
    """从配置文件读取 webhook，若不存在则返回空字符串。"""
    if not os.path.exists(config_path):
        return ""

    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except ValueError as exc:
        raise ValueError(f"{config_path} 不是有效的 JSON：{exc}")
    except OSError as exc:
        raise OSError(f"读取 {config_path} 失败：{exc}")

    if not isinstance(config, dict):
        raise ValueError(f"{config_path} 应为包含 webhook 字段的 JSON 对象。")

    webhook_url = config.get("webhook", "").strip()
    if webhook_url:
        return webhook_url

    return ""


def build_error_hint(err: urllib.error.URLError) -> str:
    """根据常见网络异常给出提示。"""
    reason = getattr(err, "reason", None)
    if isinstance(reason, socket.gaierror):
        return "DNS 解析失败，可能未联网或需放行外网访问（沙箱环境需允许网络）。"
    if isinstance(reason, socket.timeout):
        return "请求超时，请检查网络连通性或代理配置。"
    return ""


def send_feishu_message(webhook_url: str, text: str):
    """向飞书群机器人发送文本消息，返回 (status_code, response_body)，内置简单重试。"""
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    data = json.dumps(payload).encode("utf-8")
    ssl_context = build_ssl_context()
    request = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=10, context=ssl_context) as response:
                body = response.read().decode("utf-8", errors="replace")
                http_status = response.status
            break
        except urllib.error.URLError as exc:  # 网络错误重试
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            hint = build_error_hint(exc)
            if hint:
                raise urllib.error.URLError(f"{exc}; {hint}")
            raise

    if http_status >= 300:
        raise RuntimeError(f"飞书返回状态码 {http_status}: {body}")

    parsed = None
    try:
        parsed = json.loads(body)
    except ValueError:
        parsed = None

    if isinstance(parsed, dict):
        status_code = parsed.get("StatusCode")
        status_message = parsed.get("StatusMessage", "")
        if status_code is None and "code" in parsed:
            status_code = parsed.get("code")
            status_message = parsed.get("msg", "")
        if status_code not in (None, 0):
            raise RuntimeError(f"飞书返回错误码 {status_code}: {status_message or body}")

    return http_status, body


def read_feature_log_records(repo_dir: str) -> list:
    feature_log_path = os.path.join(repo_dir, FEATURE_LOG_FILENAME)
    if not os.path.exists(feature_log_path):
        return []

    diff_outputs = []
    for args in (
        ["git", "diff", "--", FEATURE_LOG_FILENAME],
        ["git", "diff", "--cached", "--", FEATURE_LOG_FILENAME],
    ):
        try:
            result = subprocess.run(
                args,
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError:
            continue
        if result.returncode == 0 and result.stdout:
            diff_outputs.append(result.stdout)

    if not diff_outputs:
        return []

    records = []
    seen = set()
    for output in diff_outputs:
        for line in output.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            text = line[1:].strip()
            if "更新记录" not in text:
                continue
            if text in seen:
                continue
            seen.add(text)
            records.append(text)
    return records


def build_message_text(repo_dir: str) -> str:
    records = read_feature_log_records(repo_dir)
    if not records:
        return MESSAGE_TEXT
    latest = records[-1]
    return MESSAGE_TEXT + "\n\nFEATURE_LOG 更新记录：\n" + latest


def main() -> int:
    webhook_env = os.environ.get("FEISHU_WEBHOOK", "").strip()
    webhook_arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILENAME)
    try:
        webhook_config = load_webhook_from_config(config_path)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    webhook_url = (
        webhook_arg or webhook_env or webhook_config
    )
    if not webhook_url:
        sys.stderr.write(
            "请通过命令行参数、环境变量 FEISHU_WEBHOOK，或 feishu_config.json（webhook 字段）提供 webhook URL。\n"
        )
        return 1

    repo_dir = os.path.dirname(os.path.abspath(__file__))
    message_text = build_message_text(repo_dir)

    try:
        http_status, resp_body = send_feishu_message(webhook_url, message_text)
    except (urllib.error.URLError, RuntimeError) as exc:
        sys.stderr.write(f"发送失败: {exc}\n")
        return 1

    print(f"飞书通知已发送，HTTP {http_status}，响应: {resp_body}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
