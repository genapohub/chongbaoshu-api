import os

WX_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"

app_config = {
    "app_id": os.getenv("WX_APP_ID", "wx217600e18466774e"),
    "app_secret": os.getenv("WX_APP_SECRET", "c12cacdc16b19168572bdac9a3fd44de"),
}

# ── 微信支付配置（APIv3） ──────────────────────────────────
wx_pay_config = {
    # 商户号信息（生产环境必填）
    "mch_id": os.getenv("WX_PAY_MCH_ID", ""),                          # 商户号
    "api_v3_key": os.getenv("WX_PAY_API_V3_KEY", ""),                   # APIv3 密钥
    "serial_no": os.getenv("WX_PAY_SERIAL_NO", ""),                     # 证书序列号
    "cert_path": os.getenv("WX_PAY_CERT_PATH", "certs/apiclient_cert.pem"),   # 私钥证书路径
    "key_path": os.getenv("WX_PAY_KEY_PATH", "certs/apiclient_key.pem"),      # 私钥文件路径
    # 回调地址（由业务端组装）
    "notify_url": os.getenv("WX_PAY_NOTIFY_URL", ""),
}
