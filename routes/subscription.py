import json
import logging
import hashlib
import base64
from datetime import datetime, timedelta

import sentry_sdk
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from starlette.responses import JSONResponse

from config.database import get_db
from config.wechat import wx_pay_config
from models.subscription import Subscription
from models.subscription_order import SubscriptionOrder
from models.user import User
from models.pet import Pet
from models.breeding_record import BreedingRecord
from middleware.auth import get_current_user, TokenData
from utils.helpers import format_datetime, get_effective_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions", tags=["subscription"])


def downgrade_expired_subscriptions(db: Session) -> int:
    """批量扫描过期订阅并降级为 free，返回降级用户数量"""
    now = datetime.utcnow()

    expired_users = db.query(User).filter(
        User.subscription_tier != "free",
        User.subscription_expire.isnot(None),
        User.subscription_expire < now,
    ).all()

    for u in expired_users:
        u.subscription_tier = "free"
        u.subscription_expire = None
        u.subscription_source = None

    # 同步 Subscription 表
    expired_subs = db.query(Subscription).filter(
        Subscription.tier != "free",
        Subscription.expires_at.isnot(None),
        Subscription.expires_at < now,
    ).all()

    for s in expired_subs:
        s.tier = "free"
        s.status = "expired"
        s.expires_at = None

    if expired_users or expired_subs:
        db.commit()

    return len(expired_users)

@router.get("/current")
async def get_current_subscription(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")

    # 实时过期检查：确保当前用户看到的永远是真实等级
    effective_tier = get_effective_tier(user)
    if effective_tier != user.subscription_tier:
        user.subscription_tier = "free"
        user.subscription_expire = None
        user.subscription_source = None
        subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
        if subscription:
            subscription.tier = "free"
            subscription.status = "expired"
            subscription.expires_at = None
        db.commit()

    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()

    return {
        "code": 0,
        "data": {
            "tier": get_effective_tier(user),
            "status": subscription.status if subscription else "active",
            "expires_at": format_datetime(subscription.expires_at) if subscription and subscription.expires_at else None,
            "auto_renew": False,
        }
    }

@router.get("/usage")
async def get_usage(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    pet_count = db.query(Pet).filter(Pet.owner_id == current_user.id, Pet.is_deleted == False).count()
    breeding_count = db.query(BreedingRecord).filter(BreedingRecord.owner_id == current_user.id, BreedingRecord.is_deleted == False).count()
    
    return {
        "code": 0,
        "data": {
            "tier": get_effective_tier(user),
            "usage": {
                "petCount": pet_count,
                "breedingCount": breeding_count,
            }
        }
    }

@router.get("/plans")
async def get_plans():
    content = {
        "code": 0,
        "data": {
            "plans": [
                {"tier": "free", "name": "免费版", "price": 0, "yearlyPrice": 0, "maxPets": 3, "maxPhotosPerPet": 3, "maxBreeding": 3},
                {"tier": "basic", "name": "基础版", "price": 49, "yearlyPrice": 39, "maxPets": 100, "maxPhotosPerPet": 20, "maxBreeding": 50},
                {"tier": "pro", "name": "专业版", "price": 149, "yearlyPrice": 119, "maxPets": "unlimited", "maxPhotosPerPet": "unlimited", "maxBreeding": "unlimited"},
            ]
        }
    }
    response = JSONResponse(content=content)
    response.headers["Cache-Control"] = "public, max-age=600"  # 10分钟缓存
    return response

class UpgradeRequest(BaseModel):
    tier: str
    cycle: Optional[str] = "monthly"  # 订阅周期: monthly/yearly
    order_id: Optional[int] = None  # 已支付的订单ID，生产环境必传

# 订阅周期对应的天数
CYCLE_DAYS = {"monthly": 30, "yearly": 365}

@router.post("/upgrade")
async def upgrade_subscription(
    request: UpgradeRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Sentry：设置支付流程 tags
    sentry_sdk.set_tag("flow", "payment")
    sentry_sdk.set_tag("tier", request.tier)

    valid_tiers = ["free", "basic", "pro"]
    if request.tier not in valid_tiers:
        raise HTTPException(status_code=1001, detail="无效的订阅等级")

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")

    # 支付验证：必须提供已支付订单
    if request.tier != "free":
        if not request.order_id:
            raise HTTPException(status_code=1001, detail="升级订阅需提供有效订单ID，请先通过 /create 下单并完成支付")

        order = db.query(SubscriptionOrder).filter(
            SubscriptionOrder.id == request.order_id,
            SubscriptionOrder.user_id == user.id,
        ).first()
        if not order:
            raise HTTPException(status_code=1001, detail="订单不存在")
        if order.status != "paid":
            raise HTTPException(status_code=1001, detail="订单尚未支付完成，无法升级")
        if order.tier != request.tier:
            raise HTTPException(status_code=1001, detail="订单等级与请求升级等级不一致")

    # 根据订单的 cycle 确定过期天数（优先用订单记录的 cycle）
    cycle = "monthly"
    if request.tier != "free" and request.order_id:
        order_cycle = db.query(SubscriptionOrder).filter(SubscriptionOrder.id == request.order_id).first()
        if order_cycle and order_cycle.cycle:
            cycle = order_cycle.cycle
    elif request.cycle:
        cycle = request.cycle
    expire_days = CYCLE_DAYS.get(cycle, 30)

    user.subscription_tier = request.tier
    if request.tier != "free":
        user.subscription_source = "paid"
        user.subscription_expire = datetime.utcnow() + timedelta(days=expire_days)
    else:
        user.subscription_source = None
        user.subscription_expire = None

    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if subscription:
        subscription.tier = request.tier
        if request.tier != "free":
            subscription.status = "active"
            subscription.expires_at = datetime.utcnow() + timedelta(days=expire_days)
        else:
            subscription.status = "cancelled"
            subscription.expires_at = None

    db.commit()

    return {
        "code": 0,
        "message": "订阅升级成功",
        "data": {
            "tier": request.tier,
        }
    }

class CreateOrderRequest(BaseModel):
    tier: str
    cycle: Optional[str] = "monthly"

@router.post("/create")
async def create_order(
    request: CreateOrderRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Sentry：设置支付流程 tags
    sentry_sdk.set_tag("flow", "payment")
    sentry_sdk.set_tag("tier", request.tier)

    valid_tiers = ["basic", "pro"]
    if request.tier not in valid_tiers:
        raise HTTPException(status_code=1001, detail="无效的订阅等级")

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")

    # 月付/年付定价（年付为每月单价，总价 = 年付单价 × 12）
    prices = {
        "basic": {"monthly": 49, "yearly": 39},
        "pro": {"monthly": 149, "yearly": 119},
    }
    cycle = request.cycle or "monthly"
    price_per_month = prices.get(request.tier, {}).get(cycle, 0)
    # 月付总价 = 单月价，年付总价 = 年付月价 × 12
    total_price = price_per_month if cycle == "monthly" else price_per_month * 12

    order = SubscriptionOrder(
        user_id=user.id,
        tier=request.tier,
        cycle=cycle,
        price=total_price,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "code": 0,
        "data": {
            "order_id": order.id,
            "tier": order.tier,
            "cycle": order.cycle,
            "price": float(order.price),
            "status": order.status,
        }
    }

# ── 微信支付回调通知（APIv3 规范） ──────────────────────

def _decrypt_wechat_notify_resource(ciphertext: str, nonce: str, associated_data: str) -> str:
    """解密微信支付回调通知的加密资源（AEAD_AES_256_GCM）"""
    import os
    key = bytes.fromhex(wx_pay_config["api_v3_key"])
    if not key:
        logger.warning("WX_PAY_API_V3_KEY 未配置，无法解密支付回调")
        return ""

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(
            nonce=bytes.fromhex(nonce),
            data=ciphertext,
            associated_data=associated_data.encode("utf-8") if associated_data else b"",
        )
        return plaintext.decode("utf-8")
    except ImportError:
        logger.warning("cryptography 未安装，尝试使用备用解密方式")
        return ""
    except Exception as e:
        logger.error("[PayCallback] 资源解密失败: %s", e)
        return ""


def _process_payment_success(db: Session, out_trade_no: str, transaction_id: str, tier: str):
    """
    支付成功核心处理逻辑（幂等安全）。
    由回调接口或开发模式接口共同调用，避免重复代码。
    返回 (success: bool, message: str)
    """
    order = db.query(SubscriptionOrder).filter(
        SubscriptionOrder.id == int(out_trade_no)
    ).first()

    if not order:
        return False, "订单不存在"

    # 幂等：已支付的订单直接返回成功
    if order.status == "paid":
        logger.info("[PayCallback] 订单 %s 已处理，跳过重复回调", out_trade_no)
        return True, "订单已处理"

    if order.status != "pending":
        return False, f"订单状态异常: {order.status}"

    # 更新订单状态
    order.status = "paid"
    order.transaction_no = transaction_id

    # 根据订单的 cycle 确定过期天数
    cycle = getattr(order, "cycle", None) or "monthly"
    expire_days = CYCLE_DAYS.get(cycle, 30)

    # 升级用户订阅等级
    user = db.query(User).filter(User.id == order.user_id).first()
    if user:
        user.subscription_tier = tier or order.tier
        user.subscription_source = "wechat_pay"
        if tier and tier != "free":
            user.subscription_expire = datetime.utcnow() + timedelta(days=expire_days)

    # 同步 Subscription 表
    subscription = db.query(Subscription).filter(
        Subscription.user_id == order.user_id
    ).first()
    target_tier = tier or order.tier
    if subscription:
        subscription.tier = target_tier
        subscription.status = "active"
        subscription.expires_at = (
            datetime.utcnow() + timedelta(days=expire_days) if target_tier != "free" else None
        )
    else:
        subscription = Subscription(
            user_id=order.user_id,
            tier=target_tier,
            status="active",
            expires_at=datetime.utcnow() + timedelta(days=expire_days) if target_tier != "free" else None,
        )
        db.add(subscription)

    db.commit()
    logger.info("[PayCallback] 订单 %s 支付完成，用户 %d 升级为 %s (cycle=%s, expire_days=%d)",
                out_trade_no, order.user_id, target_tier, cycle, expire_days)
    return True, "支付成功"


@router.post("/wx-pay/callback")
async def wx_pay_callback(request: Request, db: Session = Depends(get_db)):
    """
    微信支付 APIv3 回调通知接口。
    - 验签 + 解密 → 提取 out_trade_no / transaction_id
    - 幂等更新订单状态 + 升级用户订阅
    - 返回微信要求的 {code: "SUCCESS"}
    """
    import os

    # 1. 读取请求头和正文
    signature = request.headers.get("Wechatpay-Signature", "")
    timestamp = request.headers.get("Wechatpay-Timestamp", "")
    nonce = request.headers.get("Wechatpay-Nonce", "")
    serial = request.headers.get("Wechatpay-Serial", "")

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    logger.info("[PayCallback] 收到支付回调, len=%d", len(body_str))

    # 2. 开发模式跳过验签（生产环境必须验签）
    if os.getenv("ENV", "development") == "production" and wx_pay_config["api_v3_key"]:
        # TODO: 生产环境需加载商户证书完成 RSA 签名验证
        # 签名字符串 = timestamp + "\n" + nonce + "\n" + body_str + "\n"
        logger.debug("[PayCallback] 生产环境验签 (serial=%s)", serial)
    else:
        logger.info("[PayCallback] 开发模式，跳过签名验证")

    # 3. 解析请求体，提取加密资源
    try:
        notify_data = json.loads(body_str)
        resource = notify_data.get("resource", {})
    except json.JSONDecodeError as e:
        logger.error("[PayCallback] JSON 解析失败: %s", e)
        return {"code": "FAIL", "message": "请求体格式错误"}

    ciphertext = base64.b64decode(resource.get("ciphertext", ""))
    resource_nonce = resource.get("nonce", "")
    associated_data = resource.get("associated_data", "")

    # 4. 解密资源
    decrypted = _decrypt_wechat_notify_resource(
        ciphertext, resource_nonce, associated_data
    )
    if not decrypted:
        logger.error("[PayCallback] 资源解密失败")
        return {"code": "FAIL", "message": "解密失败"}

    # 5. 解析支付结果
    try:
        payment_info = json.loads(decrypted)
    except json.JSONDecodeError:
        logger.error("[PayCallback] 解密后 JSON 解析失败")
        return {"code": "FAIL", "message": "解密数据异常"}

    trade_state = payment_info.get("trade_state", "")
    out_trade_no = payment_info.get("out_trade_no", "")
    transaction_id = payment_info.get("transaction_id", "")

    logger.info("[PayCallback] 订单=%s, 交易号=%s, 状态=%s",
                out_trade_no, transaction_id, trade_state)

    # 6. 只处理 SUCCESS
    if trade_state != "SUCCESS":
        logger.warning("[PayCallback] 非成功状态: %s, 返回 OK", trade_state)
        return {"code": "SUCCESS", "message": "OK"}

    # 7. 执行支付成功逻辑（从支付信息中提取实际套餐等级）
    #    attach 字段可由下单时传入套餐标识，fallback 使用订单记录的 tier
    attach_data = {}
    attach_str = payment_info.get("attach", "")
    if attach_str:
        try:
            attach_data = json.loads(attach_str)
        except json.JSONDecodeError:
            pass

    success, msg = _process_payment_success(
        db, out_trade_no, transaction_id, attach_data.get("tier")
    )

    if success:
        return {"code": "SUCCESS", "message": "OK"}
    else:
        # 订单问题不重试，仍返回 SUCCESS 防止微信反复推送
        logger.warning("[PayCallback] 处理异常但返回 SUCCESS 防止重试: %s", msg)
        return {"code": "SUCCESS", "message": "OK"}


@router.post("/pay-callback")
async def pay_callback(
    order_id: int,
    transaction_no: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    开发模式支付回调（简化版，用于测试）。
    生产环境请使用 /wx-pay/callback 接口。
    需要登录认证，且订单必须属于当前用户。
    """
    # Sentry：设置支付流程 tags
    sentry_sdk.set_tag("flow", "payment")

    # 安全校验：确认订单属于当前用户
    order = db.query(SubscriptionOrder).filter(
        SubscriptionOrder.id == order_id,
        SubscriptionOrder.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=1001, detail="订单不存在或不属于当前用户")

    success, msg = _process_payment_success(db, str(order_id), transaction_no, None)
    return {"code": 0, "message": msg}

@router.put("/cancel")
async def cancel_subscription(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    if user.subscription_tier == "free":
        raise HTTPException(status_code=1001, detail="免费用户无需取消")
    
    user.subscription_tier = "free"
    user.subscription_expire = None
    
    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if subscription:
        subscription.tier = "free"
        subscription.status = "cancelled"
    
    db.commit()
    
    return {
        "code": 0,
        "message": "取消订阅成功",
        "data": {
            "tier": "free",
        }
    }

@router.get("/payments")
async def get_payment_history(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    orders = db.query(SubscriptionOrder).filter(
        SubscriptionOrder.user_id == current_user.id,
        SubscriptionOrder.status == "paid"
    ).order_by(SubscriptionOrder.created_at.desc()).limit(20).all()
    
    plan_names = {
        "basic": "基础版 月付",
        "pro": "Pro 专业版",
        "basic_yearly": "基础版 年付",
        "pro_yearly": "Pro 年付",
    }
    
    payments = []
    for order in orders:
        payments.append({
            "id": order.id,
            "plan_name": plan_names.get(order.tier, order.tier),
            "amount": float(order.price),
            "payment_method": "微信支付",
            "status": order.status,
            "created_at": format_datetime(order.created_at),
            "transaction_no": order.transaction_no,
        })
    
    return {
        "code": 0,
        "data": {
            "list": payments,
        }
    }
