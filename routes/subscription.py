from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from config.database import SessionLocal
from models.subscription import Subscription
from models.subscription_order import SubscriptionOrder
from models.user import User
from models.pet import Pet
from models.breeding_record import BreedingRecord
from middleware.auth import get_current_user, TokenData

router = APIRouter(prefix="/api/subscriptions", tags=["subscription"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def format_datetime(dt):
    """格式化datetime为字符串"""
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return None

@router.get("/current")
async def get_current_subscription(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    
    return {
        "code": 0,
        "data": {
            "tier": user.subscription_tier,
            "status": subscription.status if subscription else "active",
            "expires_at": subscription.expires_at if subscription else None,
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
            "tier": user.subscription_tier,
            "usage": {
                "petCount": pet_count,
                "breedingCount": breeding_count,
            }
        }
    }

@router.get("/plans")
async def get_plans():
    return {
        "code": 0,
        "data": {
            "plans": [
                {"tier": "free", "name": "免费版", "price": 0, "maxPets": 3, "maxPhotosPerPet": 3, "maxBreeding": 3},
                {"tier": "basic", "name": "基础版", "price": 49, "maxPets": 100, "maxPhotosPerPet": 20, "maxBreeding": 50},
                {"tier": "pro", "name": "专业版", "price": 149, "maxPets": "unlimited", "maxPhotosPerPet": "unlimited", "maxBreeding": "unlimited"},
            ]
        }
    }

class UpgradeRequest(BaseModel):
    tier: str

@router.post("/upgrade")
async def upgrade_subscription(
    request: UpgradeRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    valid_tiers = ["free", "basic", "pro"]
    if request.tier not in valid_tiers:
        raise HTTPException(status_code=1001, detail="无效的订阅等级")
    
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    user.subscription_tier = request.tier
    db.commit()
    
    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if subscription:
        subscription.tier = request.tier
    
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
    valid_tiers = ["basic", "pro"]
    if request.tier not in valid_tiers:
        raise HTTPException(status_code=1001, detail="无效的订阅等级")
    
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    prices = {"basic": 49, "pro": 149}
    price = prices.get(request.tier, 0)
    
    order = SubscriptionOrder(
        user_id=user.id,
        tier=request.tier,
        price=price,
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
            "price": float(order.price),
            "status": order.status,
        }
    }

@router.post("/pay-callback")
async def pay_callback(
    order_id: int,
    transaction_no: str,
    db: Session = Depends(get_db)
):
    order = db.query(SubscriptionOrder).filter(SubscriptionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.status != "pending":
        return {"code": 0, "message": "订单已处理"}
    
    order.status = "paid"
    order.transaction_no = transaction_no
    
    user = db.query(User).filter(User.id == order.user_id).first()
    if user:
        user.subscription_tier = order.tier
        if order.tier != "free":
            expires = datetime.now() + timedelta(days=30)
            user.subscription_expire = expires
    
    subscription = db.query(Subscription).filter(Subscription.user_id == order.user_id).first()
    if subscription:
        subscription.tier = order.tier
        subscription.status = "active"
        if order.tier != "free":
            subscription.expires_at = datetime.now() + timedelta(days=30)
    else:
        subscription = Subscription(
            user_id=order.user_id,
            tier=order.tier,
            status="active",
            expires_at=datetime.now() + timedelta(days=30) if order.tier != "free" else None,
        )
        db.add(subscription)
    
    db.commit()
    
    return {"code": 0, "message": "支付成功"}

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
        "basic": "Basic 月付",
        "pro": "Pro 专业版",
        "basic_yearly": "Basic 年付",
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
