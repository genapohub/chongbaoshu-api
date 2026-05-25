"""
认证相关接口测试
- 微信登录（DEV_MODE）
- 手机号登录（DEV_MODE）
- 获取/更新 profile
- 未登录访问受保护接口
"""
import pytest


class TestWxLogin:
    """微信登录"""

    def test_wx_login_success(self, client):
        resp = client.post("/api/auth/wx-login", json={"code": "test_code"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "token" in data["data"]
        assert "user" in data["data"]

    def test_wx_login_missing_code(self, client):
        resp = client.post("/api/auth/wx-login", json={})
        assert resp.status_code == 400  # 参数验证失败

    def test_wx_login_empty_code(self, client):
        resp = client.post("/api/auth/wx-login", json={"code": ""})
        assert resp.status_code == 400


class TestPhoneLogin:
    """手机号登录"""

    def test_phone_login_dev_mode(self, client):
        """开发模式用 123456 验证码直接登录"""
        resp = client.post("/api/auth/phone-login", json={
            "phone": "13800138000",
            "code": "123456"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "token" in data["data"]

    def test_phone_login_invalid_code(self, client):
        resp = client.post("/api/auth/phone-login", json={
            "phone": "13800138000",
            "code": "000000"
        })
        # 非开发验证码应失败
        assert resp.status_code == 400

    def test_send_code(self, client):
        resp = client.post("/api/auth/send-code", json={"phone": "13800138000"})
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_send_code_invalid_phone(self, client):
        resp = client.post("/api/auth/send-code", json={"phone": "123"})
        assert resp.status_code == 400


class TestProfile:
    """用户资料"""

    def test_get_profile_authenticated(self, auth_client):
        resp = auth_client.get("/api/auth/profile")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "id" in data
        assert "nickname" in data
        assert "subscription_tier" in data

    def test_get_profile_unauthenticated(self, client):
        resp = client.get("/api/auth/profile")
        assert resp.status_code == 401

    def test_get_limits(self, auth_client):
        resp = auth_client.get("/api/auth/limits")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tier"] == "free"
        assert "maxPets" in data

    def test_get_limits_unauthenticated(self, client):
        resp = client.get("/api/auth/limits")
        assert resp.status_code == 401


class TestDashboard:
    """工作台"""

    def test_dashboard_authenticated(self, auth_client):
        resp = auth_client.get("/api/auth/dashboard")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "user" in data
        assert "stats" in data
        assert "limits" in data

    def test_dashboard_unauthenticated(self, client):
        resp = client.get("/api/auth/dashboard")
        assert resp.status_code == 401

    def test_dashboard_stats_values(self, auth_client):
        """dashboard 应返回正确的统计数据初始值"""
        resp = auth_client.get("/api/auth/dashboard")
        assert resp.status_code == 200
        stats = resp.json()["data"]["stats"]
        assert stats["petCount"] == 0
        assert stats["breedingCount"] == 0
        assert stats["healthCount"] == 0

    def test_dashboard_recent_activities(self, auth_client):
        """dashboard 应包含最近动态列表"""
        resp = auth_client.get("/api/auth/dashboard")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "recentActivities" in data
        assert isinstance(data["recentActivities"], list)

    def test_dashboard_upcoming_reminders(self, auth_client):
        """dashboard 应包含提醒列表"""
        resp = auth_client.get("/api/auth/dashboard")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "upcomingReminders" in data
        assert "dueBreedings" in data


class TestLimitsExtended:
    """Limits 接口扩展测试"""

    def test_limits_current_pets(self, auth_client):
        resp = auth_client.get("/api/auth/limits")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["currentPets"] == 0

    def test_limits_max_pets_value(self, auth_client):
        """免费用户 maxPets 应为 3"""
        resp = auth_client.get("/api/auth/limits")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["maxPets"] == 3

    def test_limits_after_creating_pet(self, auth_client):
        """创建宠物后 currentPets 应增加"""
        auth_client.post("/api/pets", data={"name": "测试犬", "species": "dog"})
        resp = auth_client.get("/api/auth/limits")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["currentPets"] == 1


class TestProfileUpdate:
    """更新用户资料扩展测试"""

    def test_update_nickname(self, auth_client):
        resp = auth_client.put("/api/auth/profile", data={"nickname": "新昵称"})
        assert resp.status_code == 200
        assert resp.json()["data"]["nickname"] == "新昵称"

    def test_update_kennel_info(self, auth_client):
        resp = auth_client.put("/api/auth/profile", data={
            "kennel_name": "测试犬舍",
            "kennel_address": "测试地址",
            "kennel_intro": "这是一家测试犬舍",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["kennel_name"] == "测试犬舍"

    def test_update_remind_settings(self, auth_client):
        resp = auth_client.put("/api/auth/profile", data={
            "remind_vaccine": True,
            "remind_deworm": False,
            "remind_vaccine_days": 7,
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["remind_vaccine"] is True
        assert data["remind_deworm"] is False
