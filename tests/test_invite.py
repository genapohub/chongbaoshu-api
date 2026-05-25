"""
邀请码获取、兑换、记录、统计测试
"""
import pytest


class TestInviteCode:
    """邀请码"""

    def test_get_invite_code(self, auth_client):
        resp = auth_client.get("/api/invite/code")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "invite_code" in data
        assert len(data["invite_code"]) > 0

    def test_get_invite_code_unauthenticated(self, client):
        resp = client.get("/api/invite/code")
        assert resp.status_code == 401


class TestInviteRedeem:
    """兑换邀请码"""

    def test_redeem_self_code_fails(self, auth_client):
        """不能兑换自己的邀请码"""
        code_resp = auth_client.get("/api/invite/code")
        my_code = code_resp.json()["data"]["invite_code"]
        resp = auth_client.post("/api/invite/redeem", json={"code": my_code})
        assert resp.status_code == 400

    def test_redeem_empty_code(self, auth_client):
        resp = auth_client.post("/api/invite/redeem", json={"code": ""})
        assert resp.status_code == 400

    def test_redeem_nonexistent_code(self, auth_client):
        resp = auth_client.post("/api/invite/redeem", json={"code": "NOTEXIST"})
        assert resp.status_code == 404

    def test_redeem_unauthenticated(self, client):
        resp = client.post("/api/invite/redeem", json={"code": "ANYCODE"})
        assert resp.status_code == 401


class TestInviteRecords:
    """邀请记录"""

    def test_get_invite_records(self, auth_client):
        resp = auth_client.get("/api/invite/records")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "list" in data
        assert "total" in data

    def test_get_invite_records_unauthenticated(self, client):
        resp = client.get("/api/invite/records")
        assert resp.status_code == 401


class TestInviteStats:
    """邀请统计"""

    def test_get_invite_stats(self, auth_client):
        resp = auth_client.get("/api/invite/stats")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "total_invites" in data
        assert "redeemed_invites" in data
        assert "total_reward_days" in data

    def test_get_invite_stats_unauthenticated(self, client):
        resp = client.get("/api/invite/stats")
        assert resp.status_code == 401
