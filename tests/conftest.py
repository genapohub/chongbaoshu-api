"""
宠宝树 API 测试公共 fixtures
- 使用 SQLite 内存数据库（StaticPool 共享连接），不污染生产数据
- 自动创建/销毁表
- 提供已认证的 client（DEV_MODE 登录）
- 测试环境禁用速率限制，避免测试间状态干扰
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 必须在 import app 之前设定环境变量
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_pytest_only_do_not_use_in_prod")
os.environ.setdefault("DB_DIALECT", "sqlite")
os.environ.setdefault("DB_STORAGE", ":memory:")
os.environ.setdefault("CORS_ORIGINS", "*")

# ── 在导入 app 之前禁用速率限制 ──────────────────────────────
# slowapi 的内存限流器跨测试共享状态，并行测试时会触发 429
# 必须在 main.py / routes/auth.py 被导入前 monkey-patch Limiter.limit
from slowapi import Limiter
_original_limit = Limiter.limit
Limiter.limit = lambda self, *args, **kwargs: (lambda f: f)

from config.database import Base, get_db
from main import app

# 全局限流器也设为空操作
if hasattr(app.state, 'limiter') and app.state.limiter:
    app.state.limiter.limit = lambda *args, **kwargs: (lambda f: f)

# 内存数据库 —— StaticPool 确保所有连接共享同一个内存 DB
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """每个测试前建表，测试后删表"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """未认证的 test client"""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """已认证的 test client（DEV_MODE 模拟登录）"""
    resp = client.post("/api/auth/wx-login", json={"code": "test_pytest"})
    assert resp.status_code == 200
    token = resp.json()["data"]["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
def auth_user_id(auth_client):
    """返回当前登录用户 ID"""
    resp = auth_client.get("/api/auth/profile")
    assert resp.status_code == 200
    return resp.json()["data"]["id"]
