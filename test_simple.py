#!/usr/bin/env python3
"""简化测试脚本"""
import requests

BASE_URL = "http://localhost:3001"

print("=" * 70)
print("宠宝树V1.1 - 简化API测试")
print("=" * 70)

# 测试1: 健康检查
print("\n1. 健康检查...")
try:
    r = requests.get(f"{BASE_URL}/api/health-check", timeout=5)
    print(f"   状态码: {r.status_code}")
    print(f"   响应: {r.text[:100]}")
    assert r.status_code == 200
    print("   ✅ 通过")
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 测试2: 登录
print("\n2. 微信登录...")
try:
    r = requests.post(f"{BASE_URL}/api/auth/wx-login", json={"code": "test_simple"}, timeout=5)
    print(f"   状态码: {r.status_code}")
    print(f"   响应: {r.text[:150]}")
    assert r.status_code == 200
    data = r.json()
    token = data["data"]["token"]
    print(f"   ✅ 通过，Token: {token[:30]}...")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# 测试3: 添加宠物
print("\n3. 添加宠物...")
try:
    pet_data = {"name": "TestPet", "species": "dog", "breed": "Golden", "gender": "male"}
    r = requests.post(f"{BASE_URL}/api/pets/", headers=headers, json=pet_data, timeout=5)
    print(f"   状态码: {r.status_code}")
    print(f"   响应: {r.text[:200]}")
    assert r.status_code == 200
    pet_id = r.json()["data"]["id"]
    print(f"   ✅ 通过，宠物ID: {pet_id}")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    exit(1)

# 测试4: 获取宠物列表
print("\n4. 获取宠物列表...")
try:
    r = requests.get(f"{BASE_URL}/api/pets/", headers=headers, timeout=5)
    print(f"   状态码: {r.status_code}")
    print(f"   响应: {r.text[:200]}")
    assert r.status_code == 200
    print("   ✅ 通过")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    exit(1)

# 测试5: 添加繁育记录
print("\n5. 添加繁育记录...")
try:
    breeding_data = {"mother_id": pet_id, "mate_date": "2025-01-01"}
    r = requests.post(f"{BASE_URL}/api/breeding/", headers=headers, json=breeding_data, timeout=5)
    print(f"   状态码: {r.status_code}")
    print(f"   响应: {r.text[:200]}")
    assert r.status_code == 200
    print("   ✅ 通过")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    exit(1)

# 测试6: 添加健康记录
print("\n6. 添加健康记录...")
try:
    health_data = {"pet_id": pet_id, "type": "vaccine", "vaccine_type": "rabies", "record_date": "2025-01-01"}
    r = requests.post(f"{BASE_URL}/api/health/", headers=headers, json=health_data, timeout=5)
    print(f"   状态码: {r.status_code}")
    print(f"   响应: {r.text[:200]}")
    assert r.status_code == 200
    print("   ✅ 通过")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    exit(1)

# 测试7: 获取邀请码
print("\n7. 获取邀请码...")
try:
    r = requests.get(f"{BASE_URL}/api/invite/code", headers=headers, timeout=5)
    print(f"   状态码: {r.status_code}")
    print(f"   响应: {r.text[:200]}")
    assert r.status_code == 200
    print("   ✅ 通过")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    exit(1)

# 测试8: 订阅方案
print("\n8. 订阅方案...")
try:
    r = requests.get(f"{BASE_URL}/api/subscriptions/plans", timeout=5)
    print(f"   状态码: {r.status_code}")
    print(f"   响应: {r.text[:200]}")
    assert r.status_code == 200
    print("   ✅ 通过")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    exit(1)

print("\n" + "=" * 70)
print("🎉 所有核心API测试通过！")
print("=" * 70)
print(f"\n后端运行地址: {BASE_URL}")
print(f"Swagger文档: {BASE_URL}/docs")
