"""
宠宝树 — 统一业务错误码

所有路由统一使用此模块中定义的错误码常量，替代内联的数字。
调用方式：
    from config.error_codes import Errors
    raise HTTPException(status_code=Errors.PARAM_INVALID, detail="参数错误")
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCodes:
    # ── 通用 ──
    SUCCESS: int = 0
    PARAM_INVALID: int = 1001       # 参数错误/客户端错误
    UNAUTHORIZED: int = 1002         # 未登录/Token无效
    PERMISSION_DENIED: int = 2001    # 权限不足/配额超限
    NOT_FOUND: int = 404             # 资源不存在
    SERVER_ERROR: int = 500          # 服务端错误
    DEEP_CHECK_FAILED: int = 5001    # 深度健康检查失败
    BUSINESS_ERROR: int = 5005       # 业务规则校验失败（如证书状态不允许操作）

    @classmethod
    def http_status(cls, code: int) -> int:
        """将业务错误码映射到 HTTP 状态码（用于中间件层）"""
        mapping = {
            cls.SUCCESS: 200,
            cls.PARAM_INVALID: 400,
            cls.UNAUTHORIZED: 401,
            cls.PERMISSION_DENIED: 403,
            cls.NOT_FOUND: 404,
            cls.SERVER_ERROR: 500,
            cls.DEEP_CHECK_FAILED: 500,
            cls.BUSINESS_ERROR: 400,
        }
        return mapping.get(code, 400)


Errors = ErrorCodes()
