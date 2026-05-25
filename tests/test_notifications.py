"""
通知列表、标记已读、未读数测试
"""
import pytest


class TestNotificationList:
    """通知列表"""

    def test_get_notifications_empty(self, auth_client):
        resp = auth_client.get("/api/notifications")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "list" in data
        assert "total" in data

    def test_get_notifications_unauthenticated(self, client):
        resp = client.get("/api/notifications")
        assert resp.status_code == 401


class TestNotificationRead:
    """标记已读"""

    def test_mark_read_nonexistent(self, auth_client):
        """标记不存在通知为已读"""
        resp = auth_client.put("/api/notifications/99999/read")
        assert resp.status_code == 404

    def test_mark_all_read(self, auth_client):
        resp = auth_client.put("/api/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_mark_read_unauthenticated(self, client):
        resp = client.put("/api/notifications/1/read")
        assert resp.status_code == 401


class TestNotificationUnreadCount:
    """未读数"""

    def test_get_unread_count(self, auth_client):
        resp = auth_client.get("/api/notifications/unread-count")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "count" in data

    def test_get_unread_count_unauthenticated(self, client):
        resp = client.get("/api/notifications/unread-count")
        assert resp.status_code == 401
