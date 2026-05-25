"""
订阅方案、当前订阅、用量、升级/取消/支付回调测试
"""
import pytest


class TestSubscriptionPlans:
    """订阅方案"""

    def test_get_plans_no_auth(self, client):
        """获取方案列表无需登录"""
        resp = client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "plans" in data
        assert isinstance(data["plans"], list)
        assert len(data["plans"]) >= 3  # free + basic + pro

    def test_plans_contain_expected_tiers(self, client):
        resp = client.get("/api/subscriptions/plans")
        plans = resp.json()["data"]["plans"]
        tiers = [p["tier"] for p in plans]
        assert "free" in tiers
        assert "basic" in tiers
        assert "pro" in tiers

    def test_plans_cache_header(self, client):
        """订阅方案应返回缓存头"""
        resp = client.get("/api/subscriptions/plans")
        assert resp.status_code == 200
        assert "cache-control" in resp.headers
        assert "max-age=600" in resp.headers["cache-control"]

    def test_plans_free_tier_details(self, client):
        """免费版方案应包含正确限制"""
        resp = client.get("/api/subscriptions/plans")
        plans = resp.json()["data"]["plans"]
        free_plan = next(p for p in plans if p["tier"] == "free")
        assert free_plan["maxPets"] == 3
        assert free_plan["price"] == 0


class TestCurrentSubscription:
    """当前订阅"""

    def test_get_current_subscription(self, auth_client):
        resp = auth_client.get("/api/subscriptions/current")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "tier" in data
        assert "status" in data
        assert data["tier"] == "free"

    def test_get_current_unauthenticated(self, client):
        resp = client.get("/api/subscriptions/current")
        assert resp.status_code == 401


class TestSubscriptionUsage:
    """订阅用量"""

    def test_get_usage(self, auth_client):
        resp = auth_client.get("/api/subscriptions/usage")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tier"] == "free"
        assert "usage" in data
        assert "petCount" in data["usage"]
        assert "breedingCount" in data["usage"]

    def test_get_usage_unauthenticated(self, client):
        resp = client.get("/api/subscriptions/usage")
        assert resp.status_code == 401


class TestSubscriptionUpgrade:
    """订阅升级"""

    def test_upgrade_without_order_id(self, auth_client):
        """升级需提供有效订单ID"""
        resp = auth_client.post("/api/subscriptions/upgrade", json={"tier": "basic"})
        assert resp.status_code == 400

    def test_upgrade_invalid_tier(self, auth_client):
        resp = auth_client.post("/api/subscriptions/upgrade", json={
            "tier": "invalid",
            "order_id": 1,
        })
        assert resp.status_code == 400

    def test_upgrade_unauthenticated(self, client):
        resp = client.post("/api/subscriptions/upgrade", json={"tier": "basic"})
        assert resp.status_code == 401


class TestSubscriptionCancel:
    """取消订阅"""

    def test_cancel_free_user(self, auth_client):
        """免费用户无需取消"""
        resp = auth_client.put("/api/subscriptions/cancel")
        assert resp.status_code == 400

    def test_cancel_unauthenticated(self, client):
        resp = client.put("/api/subscriptions/cancel")
        assert resp.status_code == 401


class TestSubscriptionOrder:
    """订阅订单"""

    def test_create_order_invalid_tier(self, auth_client):
        resp = auth_client.post("/api/subscriptions/create", json={"tier": "free"})
        assert resp.status_code == 400

    def test_create_order_basic(self, auth_client):
        resp = auth_client.post("/api/subscriptions/create", json={"tier": "basic"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "order_id" in data
        assert data["tier"] == "basic"
        assert data["status"] == "pending"

    def test_create_order_pro(self, auth_client):
        resp = auth_client.post("/api/subscriptions/create", json={"tier": "pro"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["price"] == 149.0

    def test_create_order_pro_yearly(self, auth_client):
        """Pro 年付订单总价应为 119×12=1428"""
        resp = auth_client.post("/api/subscriptions/create", json={"tier": "pro", "cycle": "yearly"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["price"] == 1428.0
        assert data["cycle"] == "yearly"

    def test_create_order_unauthenticated(self, client):
        resp = client.post("/api/subscriptions/create", json={"tier": "basic"})
        assert resp.status_code == 401


class TestSubscriptionPayments:
    """支付记录"""

    def test_get_payment_history(self, auth_client):
        resp = auth_client.get("/api/subscriptions/payments")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_get_payment_history_unauthenticated(self, client):
        resp = client.get("/api/subscriptions/payments")
        assert resp.status_code == 401
