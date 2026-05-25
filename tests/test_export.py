"""
导出任务创建（含 Pro 权限）测试
"""
import pytest


class TestExportCreate:
    """创建导出任务"""

    def test_create_export_free_user_denied(self, auth_client):
        """免费用户不能创建导出任务"""
        resp = auth_client.post("/api/export/tasks", json={"type": "pets"})
        assert resp.status_code == 403

    def test_create_export_invalid_type(self, auth_client):
        """免费用户即使类型不对也先被 403 拦截"""
        resp = auth_client.post("/api/export/tasks", json={"type": "invalid"})
        assert resp.status_code == 403

    def test_create_export_unauthenticated(self, client):
        resp = client.post("/api/export/tasks", json={"type": "pets"})
        assert resp.status_code == 401


class TestExportList:
    """导出任务列表"""

    def test_get_export_tasks_empty(self, auth_client):
        resp = auth_client.get("/api/export/tasks")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_get_export_tasks_unauthenticated(self, client):
        resp = client.get("/api/export/tasks")
        assert resp.status_code == 401
