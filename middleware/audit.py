"""
审计日志中间件 — 记录敏感操作到专用审计日志
覆盖操作：登录、支付、订阅变更、数据删除、权限变更
"""

import logging
import time
import json
from datetime import datetime
from fastapi import Request

audit_logger = logging.getLogger("chongbaoshu.audit")

# 需要审计的操作模式（method + path prefix）
AUDIT_PATTERNS = [
    ("POST", "/api/auth/login"),           # 登录
    ("POST", "/api/auth/register"),        # 注册
    ("POST", "/api/subscriptions/wx-pay/callback"),  # 支付回调
    ("POST", "/api/subscriptions/upgrade"),# 订阅升级
    ("PUT", "/api/subscriptions/cancel"),  # 取消订阅
    ("DELETE", "/api/pets"),               # 删除宠物
    ("DELETE", "/api/breeding"),           # 删除繁育记录
    ("POST", "/api/photos/upload"),        # 上传照片
]


def should_audit(method: str, path: str) -> bool:
    """判断请求是否需要审计记录"""
    for m, prefix in AUDIT_PATTERNS:
        if method == m and path.startswith(prefix):
            return True
    return False


async def audit_middleware(request: Request, call_next):
    """审计日志中间件函数，挂载到 app.middleware"""

    if not should_audit(request.method, request.url.path):
        return await call_next(request)

    start = time.time()
    
    # 尝试读取 body（不消费流）
    body_text = ""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            body_text = body_bytes[:2000].decode("utf-8", errors="replace")
            # 重设 body 以便后续中间件正常读取
            request._body = body_bytes
        except Exception:
            pass

    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)

    # 记录审计日志
    audit_logger.info(
        json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "")[:200],
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "body_preview": body_text[:500] if body_text else "",
        }, ensure_ascii=False)
    )

    return response
