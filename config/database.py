"""
数据库连接与 Session 管理

通过 config/env.py 自动选择数据库：
- 开发环境 → SQLite
- 生产环境 → MySQL
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.env import get_db_url, is_production

DB_URL = get_db_url()

if is_production():
    engine = create_engine(
        DB_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=False,
    )
else:
    engine = create_engine(
        DB_URL,
        connect_args={"check_same_thread": False},
        pool_size=5,
        pool_pre_ping=True,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：获取数据库 session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
