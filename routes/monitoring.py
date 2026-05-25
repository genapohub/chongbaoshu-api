"""
监控数据查询路由

提供 /api/monitoring/stats 端点，供运维面板或告警系统
查询 API 性能统计数据（请求总数、错误率、慢请求等）。
"""

from fastapi import APIRouter, Depends
from middleware.auth import get_current_user, TokenData
from middleware.monitoring import get_monitoring_stats

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/stats")
async def get_stats(
    current_user: TokenData = Depends(get_current_user),
):
    """
    获取 API 性能监控统计数据。

    需要登录认证。返回内容包括：
    - total_requests: 总请求数
    - total_errors: 5xx 错误总数
    - avg_duration_ms: 平均响应耗时（毫秒）
    - slow_threshold_ms: 慢请求判定阈值（毫秒）
    - endpoints: 按 endpoint 聚合的统计详情
    """
    stats = get_monitoring_stats()
    return {"code": 0, "data": stats}
