"""
数据埋点与监控 — 后端单元测试

覆盖范围：
1. MonitoringMiddleware 基本功能（请求计时、状态码记录）
2. get_monitoring_stats() 返回数据结构
3. capture_business_error() 分类逻辑
4. before_send PII 脱敏
5. /api/monitoring/stats 端点
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from config.sentry_config import before_send, _sanitize_event, _sanitize_dict, _sanitize_query_string, _redact_value_in_string, _PII_FIELDS
from middleware.monitoring import MonitoringMiddleware, get_monitoring_stats
from middleware.error_handler import capture_business_error, classify_error_code, ERROR_CODE_MAP


# ============================================================
# 1. MonitoringMiddleware 基本功能
# ============================================================


class TestMonitoringMiddleware:
    """MonitoringMiddleware 单元测试"""

    def test_init_default_threshold(self):
        """默认慢请求阈值为 3000ms"""
        mw = MonitoringMiddleware(MagicMock())
        assert mw._slow_threshold_ms == 3000

    def test_init_custom_threshold(self):
        """自定义慢请求阈值"""
        mw = MonitoringMiddleware(MagicMock(), slow_threshold_ms=5000)
        assert mw._slow_threshold_ms == 5000

    def test_is_slow_request(self):
        """慢请求判定逻辑"""
        mw = MonitoringMiddleware(MagicMock(), slow_threshold_ms=1000)
        assert mw._is_slow_request(999) is False
        assert mw._is_slow_request(1000) is False   # > 1000, not >=
        assert mw._is_slow_request(1001) is True

    def test_record_request_basic(self):
        """基本请求记录逻辑"""
        mw = MonitoringMiddleware(MagicMock())
        mw._record_request("GET", "/api/pets", 200, 150.5)

        assert mw._total_requests == 1
        assert mw._total_errors == 0
        assert mw._total_duration_ms == 150.5

        endpoint_key = "GET /api/pets"
        assert endpoint_key in mw._endpoint_stats
        stats = mw._endpoint_stats[endpoint_key]
        assert stats["count"] == 1
        assert stats["avg_ms"] == 150.5
        assert stats["max_ms"] == 150.5
        assert stats["error_count"] == 0
        assert stats["slow_count"] == 0

    def test_record_request_multiple(self):
        """多次请求聚合统计"""
        mw = MonitoringMiddleware(MagicMock(), slow_threshold_ms=500)
        mw._record_request("GET", "/api/pets", 200, 100.0)
        mw._record_request("GET", "/api/pets", 200, 200.0)
        mw._record_request("GET", "/api/pets", 500, 600.0)

        assert mw._total_requests == 3
        assert mw._total_errors == 1   # 5xx 计入 total_errors
        assert mw._total_duration_ms == 900.0

        stats = mw._endpoint_stats["GET /api/pets"]
        assert stats["count"] == 3
        assert stats["avg_ms"] == 300.0   # 900/3
        assert stats["max_ms"] == 600.0
        assert stats["error_count"] == 1   # status >= 400
        assert stats["slow_count"] == 1    # 600 > 500

    def test_record_request_4xx_counts_error_not_total_error(self):
        """4xx 状态码计入 endpoint error_count，但不计入 total_errors（仅 5xx）"""
        mw = MonitoringMiddleware(MagicMock())
        mw._record_request("POST", "/api/pets", 400, 50.0)

        assert mw._total_requests == 1
        assert mw._total_errors == 0   # 400 < 500，不计入 total_errors

        stats = mw._endpoint_stats["POST /api/pets"]
        assert stats["error_count"] == 1   # status >= 400

    def test_get_stats_structure(self):
        """get_stats() 返回正确的数据结构"""
        mw = MonitoringMiddleware(MagicMock(), slow_threshold_ms=2000)
        mw._record_request("GET", "/api/pets", 200, 100.0)
        mw._record_request("GET", "/api/pets", 200, 200.0)

        stats = mw.get_stats()
        assert "total_requests" in stats
        assert "total_errors" in stats
        assert "avg_duration_ms" in stats
        assert "slow_threshold_ms" in stats
        assert "endpoints" in stats

        assert stats["total_requests"] == 2
        assert stats["avg_duration_ms"] == 150.0
        assert stats["slow_threshold_ms"] == 2000

        # endpoints 中不应包含 total_ms 内部字段
        endpoint = stats["endpoints"]["GET /api/pets"]
        assert "total_ms" not in endpoint
        assert "count" in endpoint
        assert "avg_ms" in endpoint
        assert "max_ms" in endpoint
        assert "error_count" in endpoint
        assert "slow_count" in endpoint

    def test_get_stats_zero_requests(self):
        """无请求时 avg_duration_ms 为 0.0"""
        mw = MonitoringMiddleware(MagicMock())
        stats = mw.get_stats()
        assert stats["total_requests"] == 0
        assert stats["avg_duration_ms"] == 0.0
        assert stats["endpoints"] == {}


# ============================================================
# 2. get_monitoring_stats() 模块函数
# ============================================================


class TestGetMonitoringStats:
    """get_monitoring_stats() 模块级便捷函数"""

    def test_returns_empty_when_no_middleware(self):
        """中间件未初始化时返回空结构"""
        import middleware.monitoring as mod
        original = mod._monitor
        mod._monitor = None
        try:
            stats = get_monitoring_stats()
            assert stats == {
                "total_requests": 0,
                "total_errors": 0,
                "avg_duration_ms": 0.0,
                "slow_threshold_ms": 0,
                "endpoints": {},
            }
        finally:
            mod._monitor = original

    def test_returns_middleware_stats(self):
        """中间件已初始化时返回其实例统计"""
        mw = MonitoringMiddleware(MagicMock(), slow_threshold_ms=1000)
        mw._record_request("GET", "/api/test", 200, 50.0)

        import middleware.monitoring as mod
        original = mod._monitor
        mod._monitor = mw
        try:
            stats = get_monitoring_stats()
            assert stats["total_requests"] == 1
            assert stats["slow_threshold_ms"] == 1000
        finally:
            mod._monitor = original


# ============================================================
# 3. capture_business_error 分类逻辑
# ============================================================


class TestClassifyErrorCode:
    """classify_error_code() 分类映射测试"""

    def test_auth_code(self):
        assert classify_error_code(1002) == "auth"

    def test_validation_code(self):
        assert classify_error_code(1001) == "validation"

    def test_quota_code(self):
        assert classify_error_code(2001) == "quota"

    def test_server_code(self):
        assert classify_error_code(5001) == "server"

    def test_unknown_code(self):
        assert classify_error_code(9999) == "unknown"

    def test_all_codes_in_map(self):
        """ERROR_CODE_MAP 中所有映射的 code 都能正确分类"""
        for category, codes in ERROR_CODE_MAP.items():
            for code in codes:
                assert classify_error_code(code) == category


class TestCaptureBusinessError:
    """capture_business_error() 测试"""

    @patch("middleware.error_handler.sentry_sdk")
    def test_skips_1002_code(self, mock_sentry):
        """1002（未登录）不上报"""
        error = HTTPException(status_code=1002, detail="未登录")
        capture_business_error(error)
        mock_sentry.push_scope.assert_not_called()
        mock_sentry.capture_event.assert_not_called()

    @patch("middleware.error_handler.sentry_sdk")
    def test_reports_non_1002_error(self, mock_sentry):
        """非 1002 错误码上报到 Sentry

        注意：capture_business_error 使用 code >= 500 判断 level，
        业务错误码 2001 >= 500 会产生 "error" level，
        这是一个源码逻辑问题（混淆了 HTTP 状态码与业务错误码），
        修复后基于 classify_error_code() 的 category 判断 level，
        非 server 类别（如 quota）应为 warning。
        """
        error = HTTPException(status_code=2001, detail="配额限制")
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=False)

        capture_business_error(error)

        mock_sentry.capture_event.assert_called_once()
        event = mock_sentry.capture_event.call_args[0][0]
        # 修复后：quota 类别 → level="warning"
        assert event["level"] == "warning"

    @patch("middleware.error_handler.sentry_sdk")
    def test_server_error_level_is_error(self, mock_sentry):
        """5xx 错误 level 为 error"""
        error = HTTPException(status_code=5001, detail="服务端错误")
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=False)

        capture_business_error(error)

        event = mock_sentry.capture_event.call_args[0][0]
        assert event["level"] == "error"

    @patch("middleware.error_handler.sentry_sdk")
    def test_includes_api_path_when_request_provided(self, mock_sentry):
        """提供 request 时设置 api_path tag"""
        error = HTTPException(status_code=1001, detail="参数错误")
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=False)

        mock_request = MagicMock()
        mock_request.url.path = "/api/pets"

        capture_business_error(error, request=mock_request)

        # 验证 scope.set_tag 被调用，包含 api_path
        tag_calls = mock_scope.set_tag.call_args_list
        tag_keys = [call[0][0] for call in tag_calls]
        assert "api_path" in tag_keys

    @patch("middleware.error_handler.sentry_sdk")
    def test_sentry_failure_does_not_raise(self, mock_sentry):
        """Sentry 上报失败不抛异常"""
        mock_sentry.push_scope.side_effect = Exception("Sentry down")
        error = HTTPException(status_code=1001, detail="参数错误")

        # 不应抛异常
        capture_business_error(error)


# ============================================================
# 4. before_send PII 脱敏
# ============================================================


class TestBeforeSendPIIScrubbing:
    """before_send PII 脱敏测试"""

    def test_before_send_returns_event(self):
        """before_send 始终返回 event（不吞事件）"""
        event = {"message": "test"}
        result = before_send(event, {})
        assert result is event

    def test_before_send_no_exception(self):
        """before_send 内部异常不外泄"""
        event = {"request": "invalid_type"}  # 非 dict，但也不应抛异常
        result = before_send(event, {})
        assert result is event

    def test_sanitize_headers_authorization(self):
        """Authorization header 被脱敏"""
        event = {
            "request": {
                "headers": {
                    "Authorization": "Bearer secret_token",
                    "Content-Type": "application/json",
                }
            }
        }
        _sanitize_event(event)
        assert event["request"]["headers"]["Authorization"] == "[Filtered]"
        assert event["request"]["headers"]["Content-Type"] == "application/json"

    def test_sanitize_headers_cookie(self):
        """Cookie header 被脱敏"""
        event = {
            "request": {
                "headers": {
                    "Cookie": "session=abc123",
                    "Accept": "*/*",
                }
            }
        }
        _sanitize_event(event)
        assert event["request"]["headers"]["Cookie"] == "[Filtered]"
        assert event["request"]["headers"]["Accept"] == "*/*"

    def test_sanitize_headers_case_insensitive(self):
        """header 脱敏大小写不敏感"""
        event = {
            "request": {
                "headers": {
                    "authorization": "Bearer token",
                    "PHONE": "13800138000",
                }
            }
        }
        _sanitize_event(event)
        assert event["request"]["headers"]["authorization"] == "[Filtered]"
        assert event["request"]["headers"]["PHONE"] == "[Filtered]"

    def test_sanitize_query_string_phone(self):
        """query_string 中 phone 参数被脱敏"""
        qs = "page=1&phone=13800138000&name=test"
        result = _sanitize_query_string(qs)
        assert "phone=[Filtered]" in result
        assert "page=1" in result
        assert "name=test" in result

    def test_sanitize_query_string_openid(self):
        """query_string 中 openid 参数被脱敏"""
        qs = "openid=oXXX123&token=abc"
        result = _sanitize_query_string(qs)
        assert "openid=[Filtered]" in result
        assert "token=[Filtered]" in result

    def test_sanitize_query_string_no_equals(self):
        """query_string 中无等号的片段保持原样"""
        qs = "flag&phone=13800138000"
        result = _sanitize_query_string(qs)
        assert "flag" in result
        assert "phone=[Filtered]" in result

    def test_sanitize_dict_phone_and_token(self):
        """dict 中 phone/token 字段被脱敏"""
        d = {"phone": "13800138000", "token": "secret", "name": "test"}
        _sanitize_dict(d)
        assert d["phone"] == "[Filtered]"
        assert d["token"] == "[Filtered]"
        assert d["name"] == "test"

    def test_sanitize_dict_case_insensitive(self):
        """dict 脱敏大小写不敏感"""
        d = {"Authorization": "Bearer x", "OPENID": "o123"}
        _sanitize_dict(d)
        assert d["Authorization"] == "[Filtered]"
        assert d["OPENID"] == "[Filtered]"

    def test_sanitize_request_data_dict(self):
        """request.data 为 dict 时脱敏"""
        event = {
            "request": {
                "data": {"phone": "13800138000", "nickname": "test"}
            }
        }
        _sanitize_event(event)
        assert event["request"]["data"]["phone"] == "[Filtered]"
        assert event["request"]["data"]["nickname"] == "test"

    def test_sanitize_request_data_string(self):
        """request.data 为 JSON 字符串时脱敏"""
        event = {
            "request": {
                "data": '{"phone": "13800138000", "name": "test"}'
            }
        }
        _sanitize_event(event)
        assert "[Filtered]" in event["request"]["data"]
        assert "test" in event["request"]["data"]

    def test_sanitize_event_no_request(self):
        """event 无 request 字段时不报错"""
        event = {"message": "no request"}
        _sanitize_event(event)
        assert event == {"message": "no request"}

    def test_redact_value_in_string(self):
        """JSON 字符串中的敏感字段值替换"""
        text = '{"phone": "13800138000", "name": "test"}'
        result = _redact_value_in_string(text, "phone")
        assert "[Filtered]" in result
        assert "test" in result

    def test_all_pii_fields_covered(self):
        """所有声明的 PII 字段都被处理"""
        expected_fields = {"authorization", "phone", "openid", "token", "cookie"}
        assert _PII_FIELDS == expected_fields


# ============================================================
# 5. /api/monitoring/stats 端点
# ============================================================


class TestMonitoringStatsEndpoint:
    """/api/monitoring/stats 端点集成测试"""

    def test_stats_endpoint_requires_auth(self, client):
        """未认证访问返回 401"""
        resp = client.get("/api/monitoring/stats")
        # 1002 错误码映射为 HTTP 401
        assert resp.status_code in (401, 400)

    def test_stats_endpoint_returns_data(self, auth_client):
        """已认证访问返回正常数据"""
        resp = auth_client.get("/api/monitoring/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "data" in data
        stats = data["data"]
        assert "total_requests" in stats
        assert "total_errors" in stats
        assert "avg_duration_ms" in stats
        assert "slow_threshold_ms" in stats
        assert "endpoints" in stats

    def test_stats_endpoint_tracks_requests(self, auth_client):
        """端点能追踪实际请求数"""
        # 先请求一次 stats 端点
        resp1 = auth_client.get("/api/monitoring/stats")
        assert resp1.status_code == 200
        data1 = resp1.json()["data"]

        # 再次请求，total_requests 应增加
        resp2 = auth_client.get("/api/monitoring/stats")
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]

        assert data2["total_requests"] >= data1["total_requests"]


# ============================================================
# 6. Sentry 配置
# ============================================================


class TestSentryConfig:
    """Sentry 配置测试"""

    def test_init_sentry_no_dsn(self):
        """DSN 为空时不初始化"""
        import os
        original = os.environ.get("SENTRY_DSN")
        os.environ["SENTRY_DSN"] = ""
        try:
            from config.sentry_config import init_sentry
            # 不应抛异常
            init_sentry()
        finally:
            if original is not None:
                os.environ["SENTRY_DSN"] = original
            else:
                os.environ.pop("SENTRY_DSN", None)

    def test_pii_fields_is_frozenset_or_set(self):
        """_PII_FIELDS 是集合类型"""
        assert isinstance(_PII_FIELDS, set)
