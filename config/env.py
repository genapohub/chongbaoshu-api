"""
宠宝树 — 环境检测与数据库路由

根据环境变量 ENV 自动选择数据库：
- development / 未设置 → SQLite（本地开发）
- production → MySQL（生产环境）

使用方式：
    from config.env import is_production, get_db_url
"""

import logging
import os

logger = logging.getLogger(__name__)


def is_production() -> bool:
    """判断当前是否为生产环境"""
    return os.getenv("ENV", "development") == "production"


def is_development() -> bool:
    """判断当前是否为开发环境"""
    return not is_production()


def get_db_url() -> str:
    """
    根据环境返回数据库连接 URL。

    - 开发环境：使用 SQLite，默认路径 ./database.sqlite
    - 生产环境：优先使用 MySQL，从环境变量读取连接参数
      支持的环境变量名称（兼容多种部署平台）：
      - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS（标准）
      - MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD（云托管）
      必需环境变量：DB_HOST/MYSQL_HOST, DB_NAME/MYSQL_DATABASE, DB_USER/MYSQL_USER, DB_PASS/MYSQL_PASSWORD
      如果缺少 MySQL 配置，则自动降级为 SQLite（./database.sqlite）
      注意：DB_HOST 可以包含端口号，如 "host:port"，此时 DB_PORT 会被忽略
    """
    if is_production():
        host = os.getenv("DB_HOST") or os.getenv("MYSQL_HOST")
        port = os.getenv("DB_PORT") or os.getenv("MYSQL_PORT") or "3306"
        name = os.getenv("DB_NAME") or os.getenv("MYSQL_DATABASE")
        user = os.getenv("DB_USER") or os.getenv("MYSQL_USER")
        password = os.getenv("DB_PASS") or os.getenv("MYSQL_PASSWORD")

        if all([host, name, user, password]):
            if ":" in host:
                host_with_port = host
            else:
                host_with_port = f"{host}:{port}"
            return (
                f"mysql+pymysql://{user}:{password}"
                f"@{host_with_port}/{name}?charset=utf8mb4"
            )
        else:
            logger.warning(
                "[WARNING] 生产环境未配置 MySQL，自动降级为 SQLite。"
                "请设置环境变量：DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS"
            )

    storage = os.getenv("DB_STORAGE", "./database.sqlite")
    return f"sqlite:///{storage}"


def get_env_label() -> str:
    """返回当前环境的可读标签"""
    return "production" if is_production() else "development"
