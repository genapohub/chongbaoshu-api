"""
证书创建/签发/撤销（含 Pro 权限）测试
"""
import pytest


def create_pet_for_cert(client, name="证书犬", species="dog"):
    """辅助：创建宠物"""
    data = {"name": name, "species": species}
    resp = client.post("/api/pets", data=data)
    assert resp.status_code == 200
    return resp.json()["data"]


class TestCertificateCreate:
    """创建证书"""

    def test_create_certificate_free_user_denied(self, auth_client):
        """免费用户不能创建证书"""
        pet = create_pet_for_cert(auth_client)
        resp = auth_client.post(f"/api/pets/{pet['id']}/certificates", json={
            "pet_id": pet["id"],
            "generation": 3,
        })
        assert resp.status_code == 403

    def test_create_certificate_nonexistent_pet(self, auth_client):
        """免费用户对不存在宠物也先被 403 拦截"""
        resp = auth_client.post("/api/pets/99999/certificates", json={
            "pet_id": 99999,
            "generation": 3,
        })
        assert resp.status_code == 403

    def test_create_certificate_unauthenticated(self, client):
        resp = client.post("/api/pets/1/certificates", json={
            "pet_id": 1,
            "generation": 3,
        })
        assert resp.status_code == 401


class TestCertificateList:
    """证书列表"""

    def test_get_certificates_empty(self, auth_client):
        pet = create_pet_for_cert(auth_client)
        resp = auth_client.get(f"/api/pets/{pet['id']}/certificates")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_get_certificates_nonexistent_pet(self, auth_client):
        resp = auth_client.get("/api/pets/99999/certificates")
        assert resp.status_code == 404

    def test_get_certificates_unauthenticated(self, client):
        resp = client.get("/api/pets/1/certificates")
        assert resp.status_code == 401


class TestCertificateIssue:
    """签发证书"""

    def test_issue_certificate_free_user_denied(self, auth_client):
        resp = auth_client.put("/api/certificates/1/issue")
        assert resp.status_code == 403

    def test_issue_certificate_unauthenticated(self, client):
        resp = client.put("/api/certificates/1/issue")
        assert resp.status_code == 401


class TestCertificateRevoke:
    """撤销证书"""

    def test_revoke_certificate_free_user_denied(self, auth_client):
        resp = auth_client.put("/api/certificates/1/revoke", json={"reason": "测试撤销"})
        assert resp.status_code == 403

    def test_revoke_certificate_unauthenticated(self, client):
        resp = client.put("/api/certificates/1/revoke", json={"reason": "测试撤销"})
        assert resp.status_code == 401
