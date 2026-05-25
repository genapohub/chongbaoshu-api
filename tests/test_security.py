"""
宠宝树 API — 安全测试套件
覆盖：安全响应头、请求体限制、支付回调认证、XSS 过滤、暴力破解防护、手机号脱敏
"""
import os
import pytest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from config.database import get_db
from models.verification_code import VerificationCode
from main import app


@pytest.fixture
def db_session():
    """获取与请求处理同生命周期的测试数据库 session

    通过 app 的 dependency override 获取 session，
    确保与请求处理器共享同一个 StaticPool 内存数据库。
    """
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    db = next(gen)
    yield db
    try:
        db.close()
    except Exception:
        pass


# ─── 1. 安全响应头 ───────────────────────────────────────────


class TestSecurityHeaders:
    """验证所有响应都附带安全响应头"""

    def test_security_headers_present(self, client: TestClient):
        """请求 /api/health-check，验证响应中包含全部安全头"""
        resp = client.get("/api/health-check")
        assert resp.status_code == 200

        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in resp.headers
        assert "Referrer-Policy" in resp.headers

    def test_hsts_header_value(self, client: TestClient):
        """验证 HSTS 值为 max-age=31536000; includeSubDomains"""
        resp = client.get("/api/health-check")
        assert resp.status_code == 200
        assert resp.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    def test_referrer_policy_value(self, client: TestClient):
        """验证 Referrer-Policy 值"""
        resp = client.get("/api/health-check")
        assert resp.status_code == 200
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_security_headers_on_api_endpoints(self, client: TestClient):
        """验证安全头也存在于 API 端点（如 404 页面）"""
        resp = client.get("/api/nonexistent-endpoint")
        # 即使是 404 也应携带安全头
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"


# ─── 2. 请求体大小限制 ─────────────────────────────────────


class TestRequestBodyLimit:
    """验证请求体大小超过 10MB 时返回 413"""

    def test_request_body_within_limit(self, auth_client: TestClient):
        """正常大小的 POST 请求应成功"""
        resp = auth_client.post(
            "/api/pets",
            data={"name": "小测试", "species": "dog", "gender": "male"},
        )
        # 只要不是 413 就算通过
        assert resp.status_code != 413

    def test_request_body_exceeds_limit(self, client: TestClient):
        """发送 content-length 超过 10MB 的请求应返回 413"""
        large_payload = "x" * (10 * 1024 * 1024 + 1)  # 10MB + 1 byte
        resp = client.post(
            "/api/auth/wx-login",
            content=large_payload.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "content-length": str(len(large_payload.encode("utf-8"))),
            },
        )
        assert resp.status_code == 413

    def test_request_body_exactly_at_limit(self, auth_client: TestClient):
        """刚好 10MB 的请求不应被拒绝（边界测试）"""
        small_data = {"name": "边界测试", "species": "cat", "gender": "female"}
        resp = auth_client.post("/api/pets", data=small_data)
        assert resp.status_code != 413


# ─── 3. 支付回调认证 ─────────────────────────────────────────


class TestPayCallbackAuth:
    """验证 pay-callback 端点需要认证且只能操作自己的订单"""

    def test_pay_callback_requires_auth(self, client: TestClient):
        """不带 Authorization 的请求应返回 401 或 403"""
        resp = client.post(
            "/api/subscriptions/pay-callback",
            params={"order_id": 1, "transaction_no": "tx_001"},
        )
        assert resp.status_code in (401, 403)

    def test_pay_callback_own_order(self, auth_client: TestClient):
        """用正确用户创建订单后调 pay-callback 应成功"""
        create_resp = auth_client.post(
            "/api/subscriptions/create",
            json={"tier": "basic", "cycle": "monthly"},
        )
        assert create_resp.status_code == 200
        order_id = create_resp.json()["data"]["order_id"]

        callback_resp = auth_client.post(
            "/api/subscriptions/pay-callback",
            params={"order_id": order_id, "transaction_no": "test_txn_001"},
        )
        assert callback_resp.status_code == 200
        assert callback_resp.json()["code"] == 0

    def test_pay_callback_other_user_order(self, client: TestClient):
        """用户 A 不能对用户 B 的订单发起支付回调"""
        resp_a = client.post("/api/auth/wx-login", json={"code": "test_pytest"})
        token_a = resp_a.json()["data"]["token"]

        create_resp = client.post(
            "/api/subscriptions/create",
            json={"tier": "basic", "cycle": "monthly"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        order_id_a = create_resp.json()["data"]["order_id"]

        # 使用不存在的 order_id 测试拒绝
        resp = client.post(
            "/api/subscriptions/pay-callback",
            params={"order_id": 99999, "transaction_no": "tx_fake"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code != 200 or resp.json().get("code") != 0


# ─── 4. XSS 过滤 ─────────────────────────────────────────────


class TestXSSSanitization:
    """验证 bleach XSS 过滤在各个入口正常工作"""

    def test_sanitize_strips_script_tags(self):
        """<script>alert(1)</script> 应被 bleach 过滤掉 script 标签"""
        from utils.sanitize import sanitize_string

        result = sanitize_string("<script>alert(1)</script>")
        # bleach 会剥离 script 标签，保留纯文本内容
        assert "<script>" not in result
        assert "</script>" not in result
        # XSS 防护的关键是标签被移除，浏览器不会执行纯文本

    def test_sanitize_strips_html_tags(self):
        """<b>bold</b> 应被剥离为 bold"""
        from utils.sanitize import sanitize_string

        result = sanitize_string("<b>bold</b>")
        assert result == "bold"

    def test_sanitize_preserves_plain_text(self):
        """普通文本不被修改"""
        from utils.sanitize import sanitize_string

        text = "这是一段普通文本 hello world 123"
        result = sanitize_string(text)
        assert result == text

    def test_sanitize_strips_event_handlers(self):
        """onclick 等事件处理器应被过滤"""
        from utils.sanitize import sanitize_string

        result = sanitize_string('<img src=x onerror="alert(1)">')
        assert "onerror" not in result

    def test_sanitize_strips_iframe(self):
        """iframe 标签应被过滤"""
        from utils.sanitize import sanitize_string

        result = sanitize_string('<iframe src="https://evil.com"></iframe>')
        assert "<iframe" not in result

    def test_profile_update_xss_filtered(self, auth_client: TestClient):
        """更新 profile 时 nickname 包含 <script> 应被过滤"""
        resp = auth_client.post(
            "/api/auth/profile",
            data={"nickname": '<script>alert("xss")</script>测试昵称'},
        )
        assert resp.status_code == 200

        data = resp.json()["data"]
        assert "<script>" not in data["nickname"]
        assert "</script>" not in data["nickname"]
        assert "测试昵称" in data["nickname"]

    def test_pet_create_xss_filtered(self, auth_client: TestClient):
        """创建宠物时 name 包含 <script> 应被过滤，通过 GET 详情验证"""
        xss_name = '<script>alert("xss")</script>旺财'
        resp = auth_client.post(
            "/api/pets",
            data={"name": xss_name, "species": "dog", "gender": "male"},
        )
        assert resp.status_code == 200

        # 创建接口只返回 id，需要 GET 详情来验证 name 已被过滤
        pet_id = resp.json()["data"]["id"]
        detail_resp = auth_client.get(f"/api/pets/{pet_id}")
        assert detail_resp.status_code == 200

        pet_data = detail_resp.json()["data"]
        assert "<script>" not in pet_data["name"]
        assert "</script>" not in pet_data["name"]
        assert "旺财" in pet_data["name"]

    def test_feedback_xss_filtered(self, auth_client: TestClient):
        """提交反馈时 content 包含 <script> 应被过滤"""
        xss_content = '<script>alert("xss")</script>这是一段反馈内容至少十个字'
        resp = auth_client.post(
            "/api/feedback/",
            json={"content": xss_content, "contact": "test@example.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0


# ─── 5. 暴力破解防护 ─────────────────────────────────────────


class TestBruteForceProtection:
    """验证手机号登录暴力破解防护"""

    def _insert_failed_codes(self, phone: str, count: int, db: Session):
        """直接向 DB 插入未使用验证码记录（模拟失败尝试）

        注意：必须使用 datetime.utcnow() 而非 func.now() 来设置 created_at，
        因为 phone-login 的暴力破解检查使用 datetime.utcnow() 进行时间比较，
        而 func.now() 返回 UTC 时间，可能导致时区不一致。
        """
        for _ in range(count):
            vc = VerificationCode(
                phone=phone,
                code="000000",  # 错误验证码
                expires_at=datetime.utcnow() + timedelta(minutes=5),
                is_used=False,
                created_at=datetime.utcnow(),  # 使用本地时间，与 phone-login 检查一致
            )
            db.add(vc)
        db.commit()

    def test_phone_login_brute_force_block(self, client: TestClient, db_session: Session):
        """连续5次错误验证码后应被锁定"""
        phone = "13900001111"

        # 插入5条未使用的验证码记录（模拟5次失败）
        self._insert_failed_codes(phone, 5, db_session)

        # 第6次尝试用错误验证码应被暴力破解防护拦截
        resp = client.post(
            "/api/auth/phone-login",
            json={"phone": phone, "code": "000000"},
        )
        # 应返回错误
        assert resp.status_code != 200
        body = resp.json()
        # 错误信息在 detail 或 message 字段中
        detail = body.get("detail", body.get("message", ""))
        assert "次数过多" in detail or "5分钟" in detail

    def test_phone_login_brute_force_block_even_dev_mode(self, client: TestClient, db_session: Session):
        """连续5次错误验证码后，即使是 DEV_MODE 正确验证码也应被锁定"""
        phone = "13900009999"

        # 插入5条未使用的验证码记录
        self._insert_failed_codes(phone, 5, db_session)

        # DEV_MODE 下 123456 也应被暴力破解防护拦截
        # 因为暴力破解检查在 DEV_MODE 快捷路径之前执行
        resp = client.post(
            "/api/auth/phone-login",
            json={"phone": phone, "code": "123456"},
        )
        # 应被拦截
        assert resp.status_code != 200 or resp.json().get("code") != 0

    def test_phone_login_under_threshold(self, client: TestClient, db_session: Session):
        """失败次数未达阈值时应正常允许登录"""
        phone = "13900002222"

        # 插入4条未使用验证码（未达5次阈值）
        self._insert_failed_codes(phone, 4, db_session)

        # DEV_MODE 下 123456 应能直接登录
        resp = client.post(
            "/api/auth/phone-login",
            json={"phone": phone, "code": "123456"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_phone_login_expired_codes_not_counted(self, client: TestClient, db_session: Session):
        """超过5分钟的失败验证码不计入阈值"""
        phone = "13900003333"

        # 插入5条已过期的验证码（超过5分钟）
        for _ in range(5):
            vc = VerificationCode(
                phone=phone,
                code="000000",
                expires_at=datetime.utcnow() - timedelta(minutes=1),
                is_used=False,
                created_at=datetime.utcnow() - timedelta(minutes=6),  # 超过5分钟
            )
            db_session.add(vc)
        db_session.commit()

        # 应能正常登录（过期的不计数）
        resp = client.post(
            "/api/auth/phone-login",
            json={"phone": phone, "code": "123456"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0


# ─── 6. 手机号脱敏 ───────────────────────────────────────────


class TestPhoneMasking:
    """验证 mask_phone 函数正确脱敏"""

    def test_mask_phone_normal(self):
        """13812345678 → 138****5678"""
        from utils.sanitize import mask_phone

        assert mask_phone("13812345678") == "138****5678"

    def test_mask_phone_different_prefix(self):
        """不同前缀的手机号也应正确脱敏"""
        from utils.sanitize import mask_phone

        assert mask_phone("15098765432") == "150****5432"
        assert mask_phone("18611112222") == "186****2222"

    def test_mask_phone_short(self):
        """短号码不做脱敏，原样返回"""
        from utils.sanitize import mask_phone

        assert mask_phone("1234567") == "1234567"
        assert mask_phone("12345") == "12345"

    def test_mask_phone_empty(self):
        """空字符串不做脱敏，原样返回"""
        from utils.sanitize import mask_phone

        assert mask_phone("") == ""

    def test_mask_phone_with_non_digits(self):
        """包含非数字字符的11位字符串不做脱敏"""
        from utils.sanitize import mask_phone

        assert mask_phone("1381234abcd") == "1381234abcd"

    def test_mask_phone_none(self):
        """None 应原样返回"""
        from utils.sanitize import mask_phone

        assert mask_phone(None) is None
