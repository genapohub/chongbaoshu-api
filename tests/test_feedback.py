"""
反馈提交、内容长度校验测试
"""
import pytest


class TestFeedbackSubmit:
    """提交反馈"""

    def test_submit_feedback_success(self, auth_client):
        resp = auth_client.post("/api/feedback/", json={
            "content": "这是一条测试反馈内容，长度超过十个字符",
            "contact": "test@example.com",
        })
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_submit_feedback_too_short(self, auth_client):
        """反馈内容至少需要10个字符"""
        resp = auth_client.post("/api/feedback/", json={
            "content": "太短",
        })
        assert resp.status_code == 400

    def test_submit_feedback_empty_content(self, auth_client):
        resp = auth_client.post("/api/feedback/", json={
            "content": "",
        })
        assert resp.status_code == 400

    def test_submit_feedback_without_contact(self, auth_client):
        """contact 是可选的"""
        resp = auth_client.post("/api/feedback/", json={
            "content": "这是一条没有联系方式的反馈内容",
        })
        assert resp.status_code == 200

    def test_submit_feedback_unauthenticated(self, client):
        resp = client.post("/api/feedback/", json={
            "content": "未登录用户的反馈内容",
        })
        assert resp.status_code == 401
