"""
健康记录 CRUD、提醒查看测试
"""
import pytest


def create_pet_for_health(client, name="健康测试犬", species="dog"):
    """辅助：创建一只用于健康记录测试的宠物"""
    data = {"name": name, "species": species}
    resp = client.post("/api/pets", data=data)
    assert resp.status_code == 200
    return resp.json()["data"]


class TestHealthCreate:
    """创建健康记录"""

    def test_add_vaccine_record(self, auth_client):
        pet = create_pet_for_health(auth_client)
        resp = auth_client.post("/api/health", json={
            "pet_id": pet["id"],
            "type": "vaccine",
            "vaccine_type": "犬瘟热",
            "record_date": "2025-01-15",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "id" in data
        assert data["type"] == "vaccine"

    def test_add_deworm_record(self, auth_client):
        pet = create_pet_for_health(auth_client)
        resp = auth_client.post("/api/health", json={
            "pet_id": pet["id"],
            "type": "deworm",
            "deworm_type": "体内驱虫",
            "record_date": "2025-01-15",
        })
        assert resp.status_code == 200

    def test_add_health_nonexistent_pet(self, auth_client):
        resp = auth_client.post("/api/health", json={
            "pet_id": 99999,
            "type": "vaccine",
            "record_date": "2025-01-15",
        })
        assert resp.status_code == 400

    def test_add_health_unauthenticated(self, client):
        resp = client.post("/api/health", json={
            "pet_id": 1,
            "type": "vaccine",
            "record_date": "2025-01-15",
        })
        assert resp.status_code == 401


class TestHealthList:
    """健康记录列表"""

    def test_list_health_empty(self, auth_client):
        resp = auth_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["list"] == []
        assert data["total"] == 0

    def test_list_health_after_create(self, auth_client):
        pet = create_pet_for_health(auth_client)
        auth_client.post("/api/health", json={
            "pet_id": pet["id"],
            "type": "vaccine",
            "vaccine_type": "犬瘟热",
            "record_date": "2025-01-15",
        })
        resp = auth_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_list_health_filter_by_type(self, auth_client):
        pet = create_pet_for_health(auth_client)
        auth_client.post("/api/health", json={
            "pet_id": pet["id"],
            "type": "vaccine",
            "vaccine_type": "犬瘟热",
            "record_date": "2025-01-15",
        })
        auth_client.post("/api/health", json={
            "pet_id": pet["id"],
            "type": "deworm",
            "deworm_type": "体内驱虫",
            "record_date": "2025-02-01",
        })
        resp = auth_client.get("/api/health", params={"type": "vaccine"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_list_health_unauthenticated(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 401


class TestHealthUpdate:
    """更新健康记录"""

    def test_update_health_notes(self, auth_client):
        pet = create_pet_for_health(auth_client)
        create_resp = auth_client.post("/api/health", json={
            "pet_id": pet["id"],
            "type": "vaccine",
            "vaccine_type": "犬瘟热",
            "record_date": "2025-01-15",
        })
        record_id = create_resp.json()["data"]["id"]
        resp = auth_client.put(f"/api/health/{record_id}", json={"notes": "接种反应良好"})
        assert resp.status_code == 200

    def test_update_health_not_found(self, auth_client):
        resp = auth_client.put("/api/health/99999", json={"notes": "不存在"})
        assert resp.status_code == 400


class TestHealthDelete:
    """删除健康记录"""

    def test_delete_health_record(self, auth_client):
        pet = create_pet_for_health(auth_client)
        create_resp = auth_client.post("/api/health", json={
            "pet_id": pet["id"],
            "type": "vaccine",
            "vaccine_type": "犬瘟热",
            "record_date": "2025-01-15",
        })
        record_id = create_resp.json()["data"]["id"]
        resp = auth_client.delete(f"/api/health/{record_id}")
        assert resp.status_code == 200

    def test_delete_health_not_found(self, auth_client):
        resp = auth_client.delete("/api/health/99999")
        assert resp.status_code == 400


class TestHealthReminders:
    """健康提醒"""

    def test_get_reminders(self, auth_client):
        pet = create_pet_for_health(auth_client)
        auth_client.post("/api/health", json={
            "pet_id": pet["id"],
            "type": "vaccine",
            "vaccine_type": "犬瘟热",
            "record_date": "2025-01-15",
        })
        resp = auth_client.get("/api/health/reminders", params={"days": 365})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "healthReminders" in data

    def test_get_reminders_unauthenticated(self, client):
        resp = client.get("/api/health/reminders")
        assert resp.status_code == 401
