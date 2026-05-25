"""
手机号登录全流程测试
- 发送验证码
- 验证码登录
- 错误验证码
- 短手机号
"""
import pytest


class TestPhoneLoginFlow:
    """手机号登录全流程"""

    def test_send_code_then_login(self, client):
        """完整流程：发送验证码 → 用验证码登录"""
        # Step 1: 发送验证码
        send_resp = client.post("/api/auth/send-code", json={"phone": "13900139000"})
        assert send_resp.status_code == 200
        assert send_resp.json()["code"] == 0

        # Step 2: DEV_MODE 下直接用 123456 登录
        login_resp = client.post("/api/auth/phone-login", json={
            "phone": "13900139000",
            "code": "123456",
        })
        assert login_resp.status_code == 200
        data = login_resp.json()["data"]
        assert "token" in data
        assert "user" in data

    def test_send_code_invalid_phone_too_short(self, client):
        resp = client.post("/api/auth/send-code", json={"phone": "123"})
        assert resp.status_code == 400

    def test_send_code_invalid_phone_too_long(self, client):
        resp = client.post("/api/auth/send-code", json={"phone": "1234567890123"})
        assert resp.status_code == 400

    def test_phone_login_wrong_code(self, client):
        """DEV_MODE 下错误验证码应失败"""
        resp = client.post("/api/auth/phone-login", json={
            "phone": "13900139000",
            "code": "654321",
        })
        assert resp.status_code == 400

    def test_phone_login_missing_fields(self, client):
        resp = client.post("/api/auth/phone-login", json={
            "phone": "13900139000",
        })
        assert resp.status_code == 400

    def test_phone_login_empty_fields(self, client):
        resp = client.post("/api/auth/phone-login", json={
            "phone": "",
            "code": "",
        })
        assert resp.status_code == 400
