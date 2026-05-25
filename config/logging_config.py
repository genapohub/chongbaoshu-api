"""
日志配置模块 - 生产环境统一日志管理
"""
import os
import sys
import logging
import logging.handlers
from datetime import datetime


def setup_logging(app_name: str = "chongbaoshu-api"):
    """初始化统一日志配置，access log 和 error log 分离输出"""

    env = os.getenv("ENV", "development")
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # ── 日志格式 ──────────────────────────────────────────
    # 生产环境用简洁格式，开发环境用详细格式
    if env == "production":
        fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    else:
        fmt = "%(asctime)s %(levelname)s %(name)s [%(filename)s:%(lineno)d] %(message)s"

    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    # ── Root Logger ───────────────────────────────────────
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if env == "development" else logging.INFO)
    root_logger.handlers.clear()

    # 控制台输出（所有级别）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ── Access Log ────────────────────────────────────────
    access_logger = logging.getLogger("access")
    access_logger.setLevel(logging.INFO)
    access_logger.handlers.clear()
    access_logger.propagate = False

    # 按天轮转 access log，保留 30 天
    access_file = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "access.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    access_file.suffix = "%Y-%m-%d"
    access_file.setFormatter(formatter)
    access_logger.addHandler(access_file)

    # 同时输出到控制台
    access_console = logging.StreamHandler(sys.stdout)
    access_console.setFormatter(formatter)
    access_logger.addHandler(access_console)

    # ── Error Log ─────────────────────────────────────────
    error_logger = logging.getLogger("error")
    error_logger.setLevel(logging.ERROR)
    error_logger.handlers.clear()
    error_logger.propagate = False

    # 按天轮转 error log，保留 90 天
    error_file = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "error.log"),
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    error_file.suffix = "%Y-%m-%d"
    error_file.setFormatter(formatter)
    error_logger.addHandler(error_file)

    # error log 也输出到 stderr
    error_console = logging.StreamHandler(sys.stderr)
    error_console.setFormatter(formatter)
    error_logger.addHandler(error_console)

    # ── 抑制第三方库的噪音日志 ───────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if env == "development" else logging.WARNING
    )

    return {
        "access": access_logger,
        "error": error_logger,
        "root": root_logger,
    }


def get_access_logger() -> logging.Logger:
    return logging.getLogger("access")


def get_error_logger() -> logging.Logger:
    return logging.getLogger("error")
