"""
速率限制中间件 — 基于 slowapi + 内存存储
- 登录/注册接口：10次/分钟
- 文件上传接口：20次/分钟
- 通用 API 接口：60次/分钟（每用户）
"""

import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException

# ── 限流配置 ────────────────────────────────────────────────

def _get_user_id_or_ip(request: Request) -> str:
    """优先用用户 ID 做限流 key，fallback 到 IP"""
    # 尝试从认证后的 user 获取 id
    try:
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            return f"user:{user.id}"
    except Exception:
        pass
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_user_id_or_ip,
    storage_uri="memory://",
    default_limits=["60/minute"],
)

# 各场景独立限制（在路由上使用 @limiter.limit() 装饰器）
RATE_LIMITS = {
    "auth": "10/minute",       # 登录/注册/短信
    "upload": "20/minute",     # 文件上传
    "pay_callback": "30/minute", # 支付回调
    "strict": "5/minute",      # 敏感操作（改密码等）
}


def setup_rate_limit(app):
    """将限流器挂载到 FastAPI app"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
