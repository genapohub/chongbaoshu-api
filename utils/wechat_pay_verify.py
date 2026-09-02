"""微信支付 APIv3 回调验签工具

生产环境回调必须通过 RSA-SHA256 验签才允许处理：
- 验签公钥来自微信支付平台证书（商户平台下载，路径由 WX_PAY_PLATFORM_CERT_PATH 配置，
  支持 X.509 证书或裸公钥两种格式）
- 验签串 = timestamp + "\\n" + nonce + "\\n" + body + "\\n"
- 时间戳偏离当前时间超过 ±5 分钟视为重放，拒绝
- 生产环境公钥未配置时 fail closed（拒绝处理），避免验签形同虚设
"""
import base64
import logging
import os
import time

logger = logging.getLogger(__name__)

_TIMESTAMP_TOLERANCE_SECONDS = 5 * 60

# (cert_path, mtime) → public_key 对象缓存，证书轮换（文件更新）后自动重载
_key_cache = {}


def _load_platform_public_key():
    """加载微信支付平台证书/公钥，返回可验签的 public key 对象，失败返回 None"""
    cert_path = os.getenv("WX_PAY_PLATFORM_CERT_PATH", "")
    if not cert_path or not os.path.exists(cert_path):
        return None

    try:
        mtime = os.path.getmtime(cert_path)
    except OSError:
        return None

    cached = _key_cache.get(cert_path)
    if cached and cached[0] == mtime:
        return cached[1]

    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    with open(cert_path, "rb") as f:
        data = f.read()
    try:
        # 优先按 X.509 证书解析，从中提取公钥
        public_key = x509.load_pem_x509_certificate(data).public_key()
    except ValueError:
        # 兜底：直接按公钥 PEM 解析
        try:
            public_key = serialization.load_pem_public_key(data)
        except (ValueError, TypeError):
            logger.error("[PayVerify] 平台证书/公钥解析失败: %s", cert_path)
            return None

    _key_cache[cert_path] = (mtime, public_key)
    return public_key


def verify_callback_signature(signature: str, timestamp: str, nonce: str, body_str: str):
    """验证微信支付回调签名。

    返回 (ok: bool, reason: str)。生产环境验签失败一律返回 False（fail closed）。
    """
    from config.wechat import wx_pay_config

    is_production = os.getenv("ENV", "development") == "production"

    # 开发模式：未配置 APIv3 密钥时跳过验签，方便本地联调
    if not is_production and not wx_pay_config.get("api_v3_key"):
        logger.info("[PayVerify] 开发模式，跳过验签")
        return True, "dev_skip"

    platform_cert_path = os.getenv("WX_PAY_PLATFORM_CERT_PATH", "")
    if not is_production and not platform_cert_path:
        # 开发环境配置了 APIv3 密钥但没下平台证书：同样放行并提示
        logger.warning("[PayVerify] 开发模式未配置 WX_PAY_PLATFORM_CERT_PATH，跳过验签")
        return True, "dev_skip"

    # ── 以下为生产环境（或开发环境显式配置了平台证书）的强校验路径 ──

    if not signature or not timestamp or not nonce:
        return False, "missing_headers"

    try:
        ts = int(timestamp)
    except ValueError:
        return False, "invalid_timestamp"
    if abs(time.time() - ts) > _TIMESTAMP_TOLERANCE_SECONDS:
        return False, "timestamp_out_of_range"

    public_key = _load_platform_public_key()
    if public_key is None:
        # fail closed：平台公钥未配置/加载失败时拒绝处理，绝不放行
        logger.error("[PayVerify] 平台公钥未配置或加载失败，拒绝处理回调")
        return False, "platform_key_unavailable"

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    message = f"{timestamp}\n{nonce}\n{body_str}\n".encode("utf-8")
    try:
        public_key.verify(
            base64.b64decode(signature),
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True, "ok"
    except (InvalidSignature, ValueError):
        logger.warning("[PayVerify] 验签失败 (serial=%s)", "n/a")
        return False, "invalid_signature"
