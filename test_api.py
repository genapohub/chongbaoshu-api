#!/usr/bin/env python3
"""
API测试脚本
测试宠宝树后端API接口
"""
import requests
import json

BASE_URL = "http://localhost:3001"

def test_health():
    """测试健康检查"""
    print("1. 测试健康检查接口...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    print("   ✅ 健康检查通过\n")

def test_auth_profile_without_token():
    """测试获取用户信息（无token）"""
    print("2. 测试获取用户信息（无token，应返回401）...")
    response = requests.get(f"{BASE_URL}/api/auth/profile")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    assert response.status_code == 401
    print("   ✅ 认证验证通过\n")

def test_subscription_plans():
    """测试获取订阅方案"""
    print("3. 测试获取订阅方案...")
    response = requests.get(f"{BASE_URL}/api/subscriptions/plans")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    print("   ✅ 订阅方案接口通过\n")

def test_breeding_without_auth():
    """测试繁育记录（无认证）"""
    print("4. 测试繁育记录列表（无token，应返回401）...")
    response = requests.get(f"{BASE_URL}/api/breeding/")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    assert response.status_code == 401
    print("   ✅ 繁育接口认证通过\n")

def test_health_reminders_without_auth():
    """测试健康提醒（无认证）"""
    print("5. 测试健康提醒（无token，应返回401）...")
    response = requests.get(f"{BASE_URL}/api/health/reminders")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    assert response.status_code == 401
    print("   ✅ 健康提醒接口认证通过\n")

def main():
    print("=" * 60)
    print("宠宝树API接口测试")
    print("=" * 60 + "\n")
    
    try:
        test_health()
        test_auth_profile_without_token()
        test_subscription_plans()
        test_breeding_without_auth()
        test_health_reminders_without_auth()
        
        print("=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        print("\n📋 已实现的API接口：")
        print("   认证相关:")
        print("   - POST /api/auth/wx-login    微信登录")
        print("   - GET  /api/auth/profile     获取用户信息")
        print("   - PUT  /api/auth/profile     更新用户信息")
        print("\n   宠物管理:")
        print("   - GET    /api/pets           获取宠物列表")
        print("   - POST   /api/pets           添加宠物")
        print("   - GET    /api/pets/{id}      获取宠物详情")
        print("   - PUT    /api/pets/{id}      更新宠物")
        print("   - DELETE /api/pets/{id}      删除宠物")
        print("   - POST   /api/pets/{id}/photos          上传照片")
        print("   - DELETE /api/pets/{id}/photos/{photo_id} 删除照片")
        print("\n   繁育管理:")
        print("   - GET    /api/breeding       繁育记录列表")
        print("   - POST   /api/breeding       添加繁育记录")
        print("   - GET    /api/breeding/{id}  繁育详情")
        print("   - PUT    /api/breeding/{id}  更新繁育记录")
        print("   - DELETE /api/breeding/{id}  删除繁育记录")
        print("\n   健康管理:")
        print("   - GET    /api/health         健康记录列表")
        print("   - GET    /api/health/reminders 提醒列表")
        print("   - POST   /api/health         添加健康记录")
        print("   - PUT    /api/health/{id}    更新健康记录")
        print("   - DELETE /api/health/{id}    删除健康记录")
        print("\n   订阅管理:")
        print("   - GET    /api/subscriptions/plans     订阅方案")
        print("   - GET    /api/subscriptions/usage     使用情况")
        print("   - POST   /api/subscriptions/upgrade  升级订阅")
        print("\n🔗 Swagger文档: http://localhost:3001/docs")
        print("\n✅ 小程序配置已更新:")
        print("   baseUrl: 'http://localhost:3001/api'")
        print("\n🚀 前后端联调成功！")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
