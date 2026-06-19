"""腾讯云短信服务（生产环境验证码发送）"""

import os
import json
import logging
import requests
from config.env import is_production

sms_logger = logging.getLogger("sms")

# 腾讯云短信配置
SMS_SECRET_ID = os.getenv("SMS_SECRET_ID", "")
SMS_SECRET_KEY = os.getenv("SMS_SECRET_KEY", "")
SMS_SDK_APP_ID = os.getenv("SMS_SDK_APP_ID", "")
SMS_TEMPLATE_ID = os.getenv("SMS_TEMPLATE_ID", "")
SMS_SIGN = os.getenv("SMS_SIGN", "宠宝树")


def send_verification_code(phone: str, code: str) -> bool:
    """发送短信验证码。开发环境仅打印日志。"""
    if not is_production():
        sms_logger.info("[DEV] 短信验证码 (不实际发送): phone=%s code=%s", phone, code)
        return True

    if not all([SMS_SECRET_ID, SMS_SECRET_KEY, SMS_SDK_APP_ID, SMS_TEMPLATE_ID]):
        sms_logger.warning("短信配置不全，跳过发送: phone=%s", phone)
        return False

    try:
        url = "https://sms.tencentcloudapi.com/"
        import hashlib
        import hmac
        from datetime import datetime

        payload = json.dumps({
            "PhoneNumberSet": ["+86" + phone],
            "SmsSdkAppId": SMS_SDK_APP_ID,
            "TemplateId": SMS_TEMPLATE_ID,
            "SignName": SMS_SIGN,
            "TemplateParamSet": [code, "5"],
        })

        # 简易签名（生产环境建议使用腾讯云SDK）
        timestamp = int(datetime.utcnow().timestamp())
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

        headers = {
            "Content-Type": "application/json",
            "X-TC-Action": "SendSms",
            "X-TC-Version": "2021-01-11",
            "X-TC-Timestamp": str(timestamp),
        }

        resp = requests.post(url, data=payload, headers=headers, timeout=10)
        result = resp.json()

        if result.get("Response", {}).get("Error"):
            sms_logger.error("短信发送失败: %s", result["Response"]["Error"])
            return False

        sms_logger.info("短信验证码已发送: phone=%s", phone)
        return True

    except Exception as e:
        sms_logger.error("短信发送异常: %s", e)
        return False
