"""
错误处理工具模块

提供：
- error_handler: 异常处理器（ASGI 中间件）
- throw_error: 抛出业务异常的便捷方法
- classify_error_code: 业务错误码分类映射
- capture_business_error: 业务异常上报 Sentry
"""

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

import sentry_sdk


# 业务错误码分类映射
ERROR_CODE_MAP: dict = {
    "auth": [1002],        # 认证相关
    "validation": [1001],  # 参数验证
    "quota": [2001],       # 配额限制
    "server": [5001],      # 服务端错误
}


def classify_error_code(code: int) -> str:
    """将业务错误码映射为分类字符串。

    Args:
        code: 业务错误码

    Returns:
        分类字符串，如 'auth' / 'validation' / 'quota' / 'server' / 'unknown'
    """
    for category, codes in ERROR_CODE_MAP.items():
        if code in codes:
            return category
    return "unknown"


def capture_business_error(
    error: HTTPException,
    request: Request = None,
) -> None:
    """上报业务异常到 Sentry。

    仅上报非 1002（未登录）的业务错误，因为 1002 太频繁无监控价值。
    5xx 系统错误由 Sentry SDK 自动捕获，此处也做补充上报。

    Args:
        error: HTTPException 异常对象
        request: 当前请求对象（可选，用于提取 api_path）
    """
    code = error.status_code

    # 1002 是未登录，太频繁无价值，跳过
    if code == 1002:
        return

    try:
        category: str = classify_error_code(code)
        level: str = "error" if category == "server" else "warning"

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_category", category)
            scope.set_tag("error_code", str(code))

            if request:
                scope.set_tag("api_path", request.url.path)

            scope.set_extra("error_detail", error.detail)
            scope.level = level

            sentry_sdk.capture_event(
                {
                    "message": f"Business error [{category}] {code}: {error.detail}",
                    "level": level,
                    "tags": {
                        "error_category": category,
                        "error_code": str(code),
                    },
                }
            )
    except Exception:
        # Sentry 上报失败不影响业务
        pass


async def error_handler(request: Request, exc: HTTPException):
    """ASGI 异常处理器。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail}
    )


def throw_error(code: int, message: str):
    """抛出业务异常，同时上报 Sentry。

    Args:
        code: 业务错误码
        message: 错误描述

    Raises:
        HTTPException: 始终抛出
    """
    error = HTTPException(status_code=code, detail=message)
    capture_business_error(error)
    raise error
