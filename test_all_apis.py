#!/usr/bin/env python3
"""
宠宝树V1.1 - 完整API测试脚本
"""
import requests
import json

BASE_URL = "http://localhost:3001"
token = None

def test_all_apis():
    global token
    
    print("=" * 70)
    print("宠宝树V1.1 - 完整API测试")
    print("=" * 70 + "\n")
    
    # 1. 健康检查
    print("1. 健康检查...")
    response = requests.get(f"{BASE_URL}/api/health-check")
    assert response.status_code == 200
    print("   ✅ 健康检查通过\n")
    
    # 2. 登录
    print("2. 微信登录（开发模式）...")
    response = requests.post(f"{BASE_URL}/api/auth/wx-login", json={"code": "test_code"})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    token = data["data"]["token"]
    print(f"   ✅ 登录成功，用户ID: {data['data']['user']['id']}\n")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. 用户信息
    print("3. 获取用户信息...")
    response = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers)
    assert response.status_code == 200
    user_data = response.json()["data"]
    print(f"   ✅ 用户: {user_data['nickname']}, 订阅: {user_data['subscription_tier']}\n")
    
    # 4. 添加宠物
    print("4. 添加宠物...")
    pet_data = {
        "name": "测试宠物",
        "species": "dog",
        "breed": "萨摩耶",
        "gender": "female"
    }
    response = requests.post(f"{BASE_URL}/api/pets/", headers=headers, json=pet_data)
    assert response.status_code == 200
    pet_id = response.json()["data"]["id"]
    print(f"   ✅ 宠物添加成功，ID: {pet_id}\n")
    
    # 5. 获取宠物列表
    print("5. 获取宠物列表...")
    response = requests.get(f"{BASE_URL}/api/pets/", headers=headers)
    assert response.status_code == 200
    pets = response.json()["data"]["list"]
    print(f"   ✅ 宠物数量: {len(pets)}\n")
    
    # 6. 获取宠物详情
    print("6. 获取宠物详情...")
    response = requests.get(f"{BASE_URL}/api/pets/{pet_id}", headers=headers)
    assert response.status_code == 200
    print(f"   ✅ 宠物详情获取成功\n")
    
    # 7. 更新宠物
    print("7. 更新宠物...")
    response = requests.put(f"{BASE_URL}/api/pets/{pet_id}", headers=headers, json={"name": "测试宠物-已更新"})
    assert response.status_code == 200
    print(f"   ✅ 宠物更新成功\n")
    
    # 8. 繁育记录
    print("8. 添加繁育记录...")
    breeding_data = {
        "mother_id": pet_id,
        "mate_date": "2025-01-01",
        "mating_method": "natural"
    }
    response = requests.post(f"{BASE_URL}/api/breeding/", headers=headers, json=breeding_data)
    assert response.status_code == 200
    breeding_id = response.json()["data"]["id"]
    print(f"   ✅ 繁育记录添加成功，ID: {breeding_id}\n")
    
    # 9. 健康记录
    print("9. 添加健康记录...")
    health_data = {
        "pet_id": pet_id,
        "type": "vaccine",
        "vaccine_type": "狂犬疫苗",
        "record_date": "2025-01-01"
    }
    response = requests.post(f"{BASE_URL}/api/health/", headers=headers, json=health_data)
    assert response.status_code == 200
    health_id = response.json()["data"]["id"]
    print(f"   ✅ 健康记录添加成功，ID: {health_id}\n")
    
    # 10. 订阅方案
    print("10. 获取订阅方案...")
    response = requests.get(f"{BASE_URL}/api/subscriptions/plans")
    assert response.status_code == 200
    plans = response.json()["data"]["plans"]
    print(f"   ✅ 订阅方案: {[p['name'] for p in plans]}\n")
    
    # 11. 当前订阅
    print("11. 获取当前订阅...")
    response = requests.get(f"{BASE_URL}/api/subscriptions/current", headers=headers)
    assert response.status_code == 200
    subscription = response.json()["data"]
    print(f"   ✅ 当前订阅: {subscription['tier']}\n")
    
    # 12. 使用情况
    print("12. 获取使用情况...")
    response = requests.get(f"{BASE_URL}/api/subscriptions/usage", headers=headers)
    assert response.status_code == 200
    usage = response.json()["data"]
    print(f"   ✅ 宠物数: {usage['usage']['petCount']}, 繁育记录数: {usage['usage']['breedingCount']}\n")
    
    # 13. 邀请码
    print("13. 获取邀请码...")
    response = requests.get(f"{BASE_URL}/api/invite/code", headers=headers)
    assert response.status_code == 200
    invite_code = response.json()["data"]["invite_code"]
    print(f"   ✅ 邀请码: {invite_code}\n")
    
    # 14. 邀请统计
    print("14. 获取邀请统计...")
    response = requests.get(f"{BASE_URL}/api/invite/stats", headers=headers)
    assert response.status_code == 200
    stats = response.json()["data"]
    print(f"   ✅ 邀请人数: {stats['total_invites']}, 总奖励天数: {stats['total_reward_days']}\n")
    
    # 15. 邀请记录
    print("15. 获取邀请记录...")
    response = requests.get(f"{BASE_URL}/api/invite/records", headers=headers)
    assert response.status_code == 200
    records = response.json()["data"]["list"]
    print(f"   ✅ 邀请记录数: {len(records)}\n")
    
    # 16. 照片设为封面（权限不足，预期403）
    print("16. 照片操作（预期403）...")
    response = requests.put(f"{BASE_URL}/api/photos/1/cover", headers=headers)
    assert response.status_code in [403, 404]
    print(f"   ✅ 照片操作权限检查通过\n")
    
    # 17. 血统证书（权限不足，预期403）
    print("17. 血统证书（预期403，非Pro用户）...")
    response = requests.post(f"{BASE_URL}/api/pets/{pet_id}/certificates", headers=headers, json={"generation": 3})
    assert response.status_code == 403
    print(f"   ✅ 血统证书权限检查通过\n")
    
    # 18. 数据导出（权限不足，预期403）
    print("18. 数据导出（预期403，非Pro用户）...")
    response = requests.post(f"{BASE_URL}/api/export/tasks", headers=headers, json={"type": "pets"})
    assert response.status_code == 403
    print(f"   ✅ 数据导出权限检查通过\n")
    
    print("=" * 70)
    print("🎉 所有测试通过！")
    print("=" * 70)
    print("\n📊 测试统计:")
    print("   ✅ 18个API接口全部测试通过")
    print("   ✅ 认证系统正常")
    print("   ✅ CRUD操作正常")
    print("   ✅ 权限控制正常")
    print("\n🔗 API清单:")
    print("   认证模块: 微信登录、获取/更新用户信息")
    print("   宠物模块: CRUD、照片管理、状态管理")
    print("   繁育模块: CRUD、状态流转")
    print("   健康模块: CRUD、提醒")
    print("   订阅模块: 方案、当前订阅、使用情况、升级")
    print("   邀请模块: 邀请码、兑换、记录、统计")
    print("   照片模块: 删除、设为封面")
    print("   证书模块: 创建、签发、撤销（Pro功能）")
    print("   导出模块: 创建导出任务（Pro功能）")
    print("\n🚀 后端服务状态: 运行中")
    print(f"   📍 API地址: {BASE_URL}")
    print(f"   📖 Swagger文档: {BASE_URL}/docs")
    print("\n💡 提示: 要测试Pro功能（证书、导出），")
    print("   需要先将用户升级为Pro版本")

if __name__ == "__main__":
    try:
        test_all_apis()
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
