"""
宠宝树 — 环境检测与数据库路由

根据环境变量 ENV 自动选择数据库：
- development / 未设置 → SQLite（本地开发）
- production → MySQL（生产环境）

使用方式：
    from config.env import is_production, get_db_url
"""

import os


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
    - 生产环境：使用 MySQL，从环境变量读取连接参数
      必需环境变量：DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
    """
    if is_production():
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT", "3306")
        name = os.getenv("DB_NAME")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASS")

        if not all([host, name, user, password]):
            raise RuntimeError(
                "生产环境缺少数据库配置。请设置环境变量："
                "DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS"
            )

        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{host}:{port}/{name}?charset=utf8mb4"
        )
    else:
        storage = os.getenv("DB_STORAGE", "./database.sqlite")
        return f"sqlite:///{storage}"


def get_env_label() -> str:
    """返回当前环境的可读标签"""
    return "production" if is_production() else "development"
