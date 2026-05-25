"""Alembic env.py — 宠宝树项目迁移环境配置

- 自动从项目 config/database.py 读取 DB_URL，无需在 alembic.ini 硬编码连接串
- 导入所有 ORM 模型，支持 --autogenerate 自动对比 schema 差异
- SQLite 下 render_as_batch=True，以支持 ALTER TABLE 操作
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

# 把项目根目录加入 sys.path，保证能 import 项目模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 加载 .env（让 DB_DIALECT / DB_STORAGE 等变量生效）
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---- 项目数据库 URL --------------------------------------------------------
from config.database import DB_URL  # type: ignore

# ---- 导入所有模型，autogenerate 才能感知 schema ----
from config.database import Base  # type: ignore  # noqa: F401
import models  # noqa: F401  — 触发所有子模型注册到 Base.metadata

# ---- Alembic 配置 ---------------------------------------------------------
config = context.config
config.set_main_option("sqlalchemy.url", DB_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# SQLite 需要 batch 模式才能 ALTER TABLE（重建表）
_is_sqlite = DB_URL.startswith("sqlite")


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL 脚本，不实际连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库直接执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
