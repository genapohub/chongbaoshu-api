import re
import bleach


def sanitize_string(value: str) -> str:
    """使用 bleach 剥离所有 HTML 标签，防止 XSS"""
    if not value:
        return value
    return bleach.clean(str(value), tags=[], attributes=[], strip=True)


def sanitize_dict(data: dict, fields: list) -> dict:
    """对字典中指定字段进行 XSS 过滤"""
    for field in fields:
        if field in data and isinstance(data[field], str):
            data[field] = sanitize_string(data[field])
    return data


def mask_phone(phone: str) -> str:
    """手机号脱敏：13812345678 → 138****5678"""
    if phone and len(phone) == 11 and phone.isdigit():
        return phone[:3] + '****' + phone[7:]
    return phone
