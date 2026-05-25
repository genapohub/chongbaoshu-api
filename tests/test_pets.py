"""
宠物 CRUD 接口测试
- 创建、列表、详情、更新、删除
- 订阅限额校验
- 血统接口
"""
import pytest


def create_pet(client, name="TestPet", species="dog", **kwargs):
    """辅助：创建一只宠物"""
    data = {"name": name, "species": species, **kwargs}
    resp = client.post("/api/pets", data=data)
    assert resp.status_code == 200
    return resp.json()["data"]


class TestPetCreate:
    """创建宠物"""

    def test_create_pet_success(self, auth_client):
        pet = create_pet(auth_client, name="旺财", species="dog", breed="金毛")
        assert "id" in pet

    def test_create_pet_missing_name(self, auth_client):
        resp = auth_client.post("/api/pets", data={"species": "dog"})
        assert resp.status_code == 400  # name 必填

    def test_create_pet_missing_species(self, auth_client):
        resp = auth_client.post("/api/pets", data={"name": "咪咪"})
        assert resp.status_code == 400  # species 必填

    def test_create_pet_unauthenticated(self, client):
        resp = client.post("/api/pets", data={"name": "旺财", "species": "dog"})
        assert resp.status_code == 401


class TestPetList:
    """宠物列表"""

    def test_list_pets_empty(self, auth_client):
        resp = auth_client.get("/api/pets")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["list"] == []
        assert data["total"] == 0

    def test_list_pets_after_create(self, auth_client):
        create_pet(auth_client, name="旺财", species="dog")
        create_pet(auth_client, name="咪咪", species="cat")

        resp = auth_client.get("/api/pets")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert len(data["list"]) == 2

    def test_list_pets_filter_species(self, auth_client):
        create_pet(auth_client, name="旺财", species="dog")
        create_pet(auth_client, name="咪咪", species="cat")

        resp = auth_client.get("/api/pets", params={"species": "dog"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["species"] == "dog"

    def test_list_pets_unauthenticated(self, client):
        resp = client.get("/api/pets")
        assert resp.status_code == 401


class TestPetDetail:
    """宠物详情"""

    def test_get_pet_detail(self, auth_client):
        pet = create_pet(auth_client, name="旺财", species="dog", breed="金毛")
        resp = auth_client.get(f"/api/pets/{pet['id']}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "旺财"
        assert data["species"] == "dog"
        assert data["breed"] == "金毛"

    def test_get_pet_not_found(self, auth_client):
        resp = auth_client.get("/api/pets/99999")
        assert resp.status_code == 404

    def test_get_pet_unauthenticated(self, client):
        resp = client.get("/api/pets/1")
        assert resp.status_code == 401


class TestPetUpdate:
    """更新宠物"""

    def test_update_pet_name(self, auth_client):
        pet = create_pet(auth_client, name="旺财")
        resp = auth_client.put(f"/api/pets/{pet['id']}", json={"name": "发财"})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == pet["id"]

        # 验证更新成功
        detail = auth_client.get(f"/api/pets/{pet['id']}").json()["data"]
        assert detail["name"] == "发财"

    def test_update_pet_not_found(self, auth_client):
        resp = auth_client.put("/api/pets/99999", json={"name": "不存在"})
        assert resp.status_code == 404


class TestPetDelete:
    """删除宠物（软删除）"""

    def test_delete_pet(self, auth_client):
        pet = create_pet(auth_client, name="待删")
        resp = auth_client.delete(f"/api/pets/{pet['id']}")
        assert resp.status_code == 200

        # 验证列表中已无此宠物
        list_resp = auth_client.get("/api/pets")
        ids = [p["id"] for p in list_resp.json()["data"]["list"]]
        assert pet["id"] not in ids

    def test_delete_pet_not_found(self, auth_client):
        resp = auth_client.delete("/api/pets/99999")
        assert resp.status_code == 404


class TestPedigree:
    """血统信息"""

    def test_get_pedigree_free_user(self, auth_client):
        """免费用户获取血统：应返回但隐藏详情"""
        pet = create_pet(auth_client, name="旺财", species="dog")
        resp = auth_client.get(f"/api/pets/{pet['id']}/pedigree")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["is_pro"] is False
        assert data["father_name"] is None
        assert data["mother_name"] is None

    def test_get_pedigree_not_found(self, auth_client):
        resp = auth_client.get("/api/pets/99999/pedigree")
        assert resp.status_code == 404


class TestPetLimit:
    """宠物数量限额"""

    def test_free_user_pet_limit(self, auth_client):
        """免费用户创建超过 3 只宠物应被拒绝"""
        for i in range(3):
            create_pet(auth_client, name=f"Pet{i}")

        resp = auth_client.post("/api/pets", data={"name": "Pet4", "species": "dog"})
        assert resp.status_code == 403  # 2001 被映射为 403
