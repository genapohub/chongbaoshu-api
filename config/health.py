"""
深度健康检查模块 - 检测服务各组件状态
"""
import os
import time
import logging
import platform
from datetime import datetime
from config.database import engine
from sqlalchemy import text

logger = logging.getLogger("access")


async def health_check_deep() -> dict:
    """
    深度健康检查，检测：
    - 应用基本信息
    - 数据库连通性
    - 系统资源（磁盘、内存）
    - 服务运行时长
    """
    status = "ok"
    checks = {}

    # ── 1. 数据库连通性检测 ─────────────────────────────
    db_ok = False
    db_latency_ms = 0
    try:
        start = time.time()
        # engine 为同步 create_engine（非 create_async_engine），须用同步连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_latency_ms = round((time.time() - start) * 1000, 2)
        db_ok = True
    except Exception as e:
        logger.error(f"[HealthCheck] 数据库连接失败: {e}")
        status = "degraded"

    checks["database"] = {
        "status": "ok" if db_ok else "error",
        "latency_ms": db_latency_ms,
    }

    # ── 2. 磁盘空间检测 ─────────────────────────────────
    try:
        stat = os.statvfs("/")
        total_gb = round(stat.f_blocks * stat.f_frsize / (1024 ** 3), 2)
        free_gb = round(stat.f_bavail * stat.f_frsize / (1024 ** 3), 2)
        used_percent = round((1 - stat.f_bavail / stat.f_blocks) * 100, 1)

        disk_ok = used_percent < 90
        if not disk_ok and status == "ok":
            status = "degraded"

        checks["disk"] = {
            "status": "ok" if disk_ok else "warning",
            "total_gb": total_gb,
            "free_gb": free_gb,
            "used_percent": used_percent,
        }
    except Exception as e:
        logger.error(f"[HealthCheck] 磁盘检测失败: {e}")
        checks["disk"] = {"status": "error", "message": str(e)}

    # ── 3. 内存使用检测 ─────────────────────────────────
    try:
        # 跨平台内存获取
        if platform.system() == "Linux":
            with open("/proc/meminfo", "r") as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        meminfo[parts[0].rstrip(":")] = int(parts[1])
            total_mb = round(meminfo.get("MemTotal", 0) / 1024, 1)
            available_mb = round(meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) / 1024, 1)
            used_percent = round((1 - available_mb / total_mb) * 100, 1) if total_mb > 0 else 0
        else:
            # macOS / 其他系统：通过 psutil 或标记为 unavailable
            total_mb = available_mb = used_percent = 0
            try:
                import resource
                rusage = resource.getrusage(resource.RUSAGE_SELF)
                process_mb = round(rusage.ru_maxrss / 1024, 1)  # macOS 返回 bytes
                checks["memory"] = {
                    "status": "ok",
                    "note": "macOS - showing process memory only",
                    "process_maxrss_mb": process_mb,
                }
                raise StopIteration
            except Exception:
                pass

        mem_ok = used_percent < 90
        if not mem_ok and status == "ok":
            status = "degraded"

        checks["memory"] = {
            "status": "ok" if mem_ok else "warning",
            "total_mb": total_mb,
            "available_mb": available_mb,
            "used_percent": used_percent,
        }
    except StopIteration:
        pass
    except Exception as e:
        logger.error(f"[HealthCheck] 内存检测失败: {e}")
        checks.setdefault("memory", {"status": "error", "message": str(e)})

    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1.0",
        "environment": os.getenv("ENV", "development"),
        "checks": checks,
    }
