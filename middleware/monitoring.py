"""
API 性能监控中间件

基于 Starlette BaseHTTPMiddleware 实现：
- 按 endpoint 聚合请求统计（count, avg_ms, max_ms, error_count, slow_count）
- 慢请求自动上报 Sentry（level=warning）
- 排除静态文件路径不做监控
- get_stats() 方法供后续 health-check 或监控端点调用
- _monitor 模块变量 + get_monitoring_stats() 供路由层直接获取统计数据
"""

import time
from typing import Dict, Optional

import sentry_sdk
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# 不做监控的路径前缀
_EXCLUDED_PATHS = ("/uploads/", "/docs", "/openapi.json", "/redoc")

# 模块级中间件实例引用，供 get_monitoring_stats() 访问
_monitor: Optional["MonitoringMiddleware"] = None


class MonitoringMiddleware(BaseHTTPMiddleware):
    """API 性能监控中间件，自动记录请求耗时与状态码统计。"""

    def __init__(self, app, slow_threshold_ms: int = 3000):
        super().__init__(app)
        self._slow_threshold_ms: int = slow_threshold_ms
        self._endpoint_stats: Dict[str, dict] = {}
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._total_duration_ms: float = 0.0
        # 保存实例引用，供 get_monitoring_stats() 访问
        global _monitor
        _monitor = self

    async def dispatch(self, request: Request, call_next) -> Response:
        """拦截每个请求，记录耗时与统计。"""
        # 排除静态文件路径
        path: str = request.url.path
        if any(path.startswith(prefix) for prefix in _EXCLUDED_PATHS):
            return await call_next(request)

        # 1. 记录开始时间
        start: float = time.time()

        # 2. 调用下游处理
        response: Response = await call_next(request)

        # 3. 计算耗时
        duration_ms: float = round((time.time() - start) * 1000, 2)

        # 4. 记录请求统计
        method: str = request.method
        status_code: int = response.status_code
        self._record_request(method, path, status_code, duration_ms)

        # 5. 慢请求上报 Sentry
        if self._is_slow_request(duration_ms):
            try:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("slow_request", "true")
                    scope.set_tag("method", method)
                    scope.set_tag("path", path)
                    scope.set_extra("duration_ms", duration_ms)
                    scope.set_extra("status_code", status_code)
                    sentry_sdk.capture_message(
                        f"Slow request: {method} {path} took {duration_ms}ms",
                        level="warning",
                    )
            except Exception:
                # Sentry 上报失败不影响业务
                pass

        # 6. 返回 response
        return response

    def _record_request(
        self, method: str, path: str, status: int, duration_ms: float
    ) -> None:
        """按 endpoint (METHOD /path) 聚合统计。"""
        endpoint: str = f"{method} {path}"

        if endpoint not in self._endpoint_stats:
            self._endpoint_stats[endpoint] = {
                "count": 0,
                "avg_ms": 0.0,
                "max_ms": 0.0,
                "error_count": 0,
                "slow_count": 0,
                "total_ms": 0.0,
            }

        stats: dict = self._endpoint_stats[endpoint]
        stats["count"] += 1
        stats["total_ms"] += duration_ms
        stats["avg_ms"] = round(stats["total_ms"] / stats["count"], 2)
        stats["max_ms"] = max(stats["max_ms"], duration_ms)

        if status >= 400:
            stats["error_count"] += 1

        if self._is_slow_request(duration_ms):
            stats["slow_count"] += 1

        # 更新全局统计
        self._total_requests += 1
        self._total_duration_ms += duration_ms
        if status >= 500:
            self._total_errors += 1

    def _is_slow_request(self, duration_ms: float) -> bool:
        """判断是否为慢请求。"""
        return duration_ms > self._slow_threshold_ms

    def get_stats(self) -> dict:
        """返回聚合统计数据，供 health-check 或监控端点调用。"""
        avg_duration: float = (
            round(self._total_duration_ms / self._total_requests, 2)
            if self._total_requests > 0
            else 0.0
        )

        # 清理内部 total_ms 字段，只返回外部需要的字段
        endpoints: Dict[str, dict] = {}
        for endpoint, stats in self._endpoint_stats.items():
            endpoints[endpoint] = {
                "count": stats["count"],
                "avg_ms": stats["avg_ms"],
                "max_ms": stats["max_ms"],
                "error_count": stats["error_count"],
                "slow_count": stats["slow_count"],
            }

        return {
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "avg_duration_ms": avg_duration,
            "slow_threshold_ms": self._slow_threshold_ms,
            "endpoints": endpoints,
        }


def get_monitoring_stats() -> dict:
    """
    获取监控中间件统计数据（模块级便捷函数）。

    由 routes/monitoring.py 的 /api/monitoring/stats 端点调用，
    无需直接引用中间件实例。

    Returns:
        dict: 统计数据字典，如果中间件未初始化则返回空结构
    """
    if _monitor is None:
        return {
            "total_requests": 0,
            "total_errors": 0,
            "avg_duration_ms": 0.0,
            "slow_threshold_ms": 0,
            "endpoints": {},
        }
    return _monitor.get_stats()
