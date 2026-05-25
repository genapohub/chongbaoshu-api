"""
繁育记录 CRUD、状态流转、近亲检测测试
"""
import pytest


def create_pet_for_breeding(client, name="母犬", species="dog"):
    """辅助：创建一只用于繁育测试的宠物"""
    data = {"name": name, "species": species}
    resp = client.post("/api/pets", data=data)
    assert resp.status_code == 200
    return resp.json()["data"]


class TestBreedingCreate:
    """创建繁育记录"""

    def test_add_breeding_record_success(self, auth_client):
        pet = create_pet_for_breeding(auth_client, name="小白")
        resp = auth_client.post("/api/breeding", json={
            "pet_id": pet["id"],
            "mating_date": "2025-01-15",
            "mating_method": "natural",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "id" in data
        assert data["pet_id"] == pet["id"]

    def test_add_breeding_with_mother_pet_id(self, auth_client):
        """mother_pet_id 别名也应工作"""
        pet = create_pet_for_breeding(auth_client, name="花花")
        resp = auth_client.post("/api/breeding", json={
            "mother_pet_id": pet["id"],
            "mating_date": "2025-02-01",
        })
        assert resp.status_code == 200

    def test_add_breeding_missing_pet_id(self, auth_client):
        resp = auth_client.post("/api/breeding", json={
            "mating_date": "2025-01-15",
        })
        assert resp.status_code == 400

    def test_add_breeding_nonexistent_pet(self, auth_client):
        resp = auth_client.post("/api/breeding", json={
            "pet_id": 99999,
            "mating_date": "2025-01-15",
        })
        assert resp.status_code == 400

    def test_add_breeding_unauthenticated(self, client):
        resp = client.post("/api/breeding", json={
            "pet_id": 1,
            "mating_date": "2025-01-15",
        })
        assert resp.status_code == 401

    def test_add_breeding_with_due_date_calculation(self, auth_client):
        """不传 due_date 时，应根据物种自动计算"""
        pet = create_pet_for_breeding(auth_client, name="花花", species="dog")
        resp = auth_client.post("/api/breeding", json={
            "pet_id": pet["id"],
            "mating_date": "2025-01-15",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["due_date"] is not None


class TestBreedingList:
    """繁育记录列表"""

    def test_list_breeding_empty(self, auth_client):
        resp = auth_client.get("/api/breeding")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["list"] == []
        assert data["total"] == 0

    def test_list_breeding_after_create(self, auth_client):
        pet = create_pet_for_breeding(auth_client)
        auth_client.post("/api/breeding", json={
            "pet_id": pet["id"],
            "mating_date": "2025-01-15",
        })
        resp = auth_client.get("/api/breeding")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1

    def test_list_breeding_filter_by_pet(self, auth_client):
        pet1 = create_pet_for_breeding(auth_client, name="犬A")
        pet2 = create_pet_for_breeding(auth_client, name="犬B")
        auth_client.post("/api/breeding", json={
            "pet_id": pet1["id"],
            "mating_date": "2025-01-15",
        })
        resp = auth_client.get("/api/breeding", params={"pet_id": pet1["id"]})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_list_breeding_unauthenticated(self, client):
        resp = client.get("/api/breeding")
        assert resp.status_code == 401


class TestBreedingDetail:
    """繁育记录详情"""

    def test_get_breeding_detail(self, auth_client):
        pet = create_pet_for_breeding(auth_client)
        create_resp = auth_client.post("/api/breeding", json={
            "pet_id": pet["id"],
            "mating_date": "2025-01-15",
        })
        record_id = create_resp.json()["data"]["id"]
        resp = auth_client.get(f"/api/breeding/{record_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == record_id

    def test_get_breeding_not_found(self, auth_client):
        resp = auth_client.get("/api/breeding/99999")
        assert resp.status_code == 400


class TestBreedingUpdate:
    """更新繁育记录"""

    def test_update_breeding_status(self, auth_client):
        pet = create_pet_for_breeding(auth_client)
        create_resp = auth_client.post("/api/breeding", json={
            "pet_id": pet["id"],
            "mating_date": "2025-01-15",
        })
        record_id = create_resp.json()["data"]["id"]
        resp = auth_client.put(f"/api/breeding/{record_id}/status", json={"status": "pregnant"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "pregnant"

    def test_update_breeding_notes(self, auth_client):
        pet = create_pet_for_breeding(auth_client)
        create_resp = auth_client.post("/api/breeding", json={
            "pet_id": pet["id"],
            "mating_date": "2025-01-15",
        })
        record_id = create_resp.json()["data"]["id"]
        resp = auth_client.put(f"/api/breeding/{record_id}", json={"notes": "健康检查正常"})
        assert resp.status_code == 200


class TestBreedingDelete:
    """删除繁育记录"""

    def test_delete_breeding_record(self, auth_client):
        pet = create_pet_for_breeding(auth_client)
        create_resp = auth_client.post("/api/breeding", json={
            "pet_id": pet["id"],
            "mating_date": "2025-01-15",
        })
        record_id = create_resp.json()["data"]["id"]
        resp = auth_client.delete(f"/api/breeding/{record_id}")
        assert resp.status_code == 200

    def test_delete_breeding_not_found(self, auth_client):
        resp = auth_client.delete("/api/breeding/99999")
        assert resp.status_code == 400


class TestInbreedingCheck:
    """近亲检测"""

    def test_check_inbreeding_no_relation(self, auth_client):
        pet1 = create_pet_for_breeding(auth_client, name="犬A")
        pet2 = create_pet_for_breeding(auth_client, name="犬B")
        resp = auth_client.post("/api/breeding/check-inbreeding", json={
            "mother_pet_id": pet1["id"],
            "father_pet_id": pet2["id"],
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["is_inbreeding"] is False

    def test_check_inbreeding_nonexistent_pet(self, auth_client):
        pet = create_pet_for_breeding(auth_client)
        resp = auth_client.post("/api/breeding/check-inbreeding", json={
            "mother_pet_id": pet["id"],
            "father_pet_id": 99999,
        })
        assert resp.status_code == 404

    def test_check_inbreeding_unauthenticated(self, client):
        resp = client.post("/api/breeding/check-inbreeding", json={
            "mother_pet_id": 1,
            "father_pet_id": 2,
        })
        assert resp.status_code == 401
