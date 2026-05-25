"""
健康检查等通用接口测试
"""
import pytest


class TestHealthCheck:
    def test_health_check(self, client):
        resp = client.get("/api/health-check")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
