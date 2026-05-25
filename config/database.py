import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

env = os.getenv("ENV", "development")

if os.getenv("DB_DIALECT") == "mysql":
    DB_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', 3306)}/{os.getenv('DB_NAME')}"
else:
    DB_URL = f"sqlite:///{os.getenv('DB_STORAGE', './database.sqlite')}"

if os.getenv("DB_DIALECT") == "mysql":
    engine = create_engine(
        DB_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        DB_URL,
        connect_args={"check_same_thread": False},
        pool_size=5,
        pool_pre_ping=True,
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
