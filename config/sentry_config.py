import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

# ---------------------------------------------------------------------------
# Sentry 配置项 — 从环境变量读取，提供合理默认值
# ---------------------------------------------------------------------------

SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
"""Sentry 项目 DSN，为空则不初始化 SDK"""

SENTRY_ENV: str = os.getenv("SENTRY_ENV", "development")
"""运行环境标识，如 development / staging / production"""

SENTRY_RELEASE: str = os.getenv("SENTRY_RELEASE", "1.0.0")
"""版本号，建议与 Git tag 保持一致"""

SENTRY_TRACES_SAMPLE_RATE: float = float(
    os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")
)
"""性能追踪采样率，0.0 ~ 1.0"""

# 需要脱敏的 PII 字段名（小写匹配）
_PII_FIELDS = {"authorization", "phone", "openid", "token", "cookie"}


def init_sentry() -> None:
    """初始化 Sentry SDK，仅在 SENTRY_DSN 配置时生效。

    调用时机：FastAPI 应用启动时（如 main.py 中 lifespan 或模块顶层）。
    """
    if not SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENV,
        release=SENTRY_RELEASE,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        integrations=[FastApiIntegration()],
        before_send=before_send,
    )


def before_send(event: dict, hint: dict) -> dict:
    """发送前钩子：脱敏 PII 字段。

    处理范围：
    1. request.headers — 移除 Authorization / Cookie 等
    2. request.query_string — 脱敏 phone / openid / token 等
    3. request.data — 脱敏 phone / openid / token 等

    Args:
        event: Sentry 事件字典
        hint: Sentry 提示信息

    Returns:
        处理后的 Sentry 事件字典
    """
    try:
        _sanitize_event(event)
    except Exception:
        # before_send 本身不能抛异常，否则会中断 Sentry 上报
        pass
    return event


def _sanitize_event(event: dict) -> None:
    """就地脱敏事件中的 PII 字段"""

    request = event.get("request")
    if not request or not isinstance(request, dict):
        return

    # 1. 脱敏 headers
    headers = request.get("headers")
    if headers and isinstance(headers, dict):
        for key in list(headers.keys()):
            if key.lower() in _PII_FIELDS:
                headers[key] = "[Filtered]"

    # 2. 脱敏 query_string
    query_string = request.get("query_string")
    if query_string and isinstance(query_string, str):
        request["query_string"] = _sanitize_query_string(query_string)

    # 3. 脱敏 request.data（可能是字符串或字典）
    data = request.get("data")
    if data:
        if isinstance(data, dict):
            _sanitize_dict(data)
        elif isinstance(data, str):
            # 尝试简单替换敏感参数值
            for field in _PII_FIELDS:
                if field in data.lower():
                    data = _redact_value_in_string(data, field)
            request["data"] = data


def _sanitize_dict(d: dict) -> None:
    """就地脱敏字典中的 PII 字段"""
    for key in list(d.keys()):
        if key.lower() in _PII_FIELDS:
            d[key] = "[Filtered]"


def _sanitize_query_string(query_string: str) -> str:
    """脱敏 URL query string 中的敏感参数"""
    parts = query_string.split("&")
    sanitized_parts = []
    for part in parts:
        if "=" not in part:
            sanitized_parts.append(part)
            continue
        key, _ = part.split("=", 1)
        if key.lower() in _PII_FIELDS:
            sanitized_parts.append(f"{key}=[Filtered]")
        else:
            sanitized_parts.append(part)
    return "&".join(sanitized_parts)


def _redact_value_in_string(text: str, field_name: str) -> str:
    """在字符串中替换敏感字段值（简单正则替换）"""
    import re

    pattern = rf'("{field_name}"\s*:\s*")(.*?)(")'
    return re.sub(pattern, rf'\1[Filtered]\3', text, flags=re.IGNORECASE)
