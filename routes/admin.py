"""轻量管理后台 — 仅限管理员访问（Seed 期一人操作，无需独立后台系统）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from config.database import get_db
from models.user import User
from models.pet import Pet
from models.subscription import Subscription
from models.subscription_order import SubscriptionOrder
from models.verification_code import VerificationCode
from models.buyer_lead import BuyerLead
from models.pet_sale import PetSale
from config.error_codes import Errors
from middleware.auth import get_current_user, TokenData

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ── 简单的管理员校验：检查用户ID是否在白名单 ──
ADMIN_USER_IDS = {1}  # 你自己的用户ID

def require_admin(current_user: TokenData = Depends(get_current_user)):
    if current_user.id not in ADMIN_USER_IDS:
        raise HTTPException(status_code=Errors.PERMISSION_DENIED, detail="无管理权限")
    return current_user

@router.get("/dashboard", dependencies=[Depends(require_admin)])
async def admin_dashboard(db: Session = Depends(get_db)):
    """管理看板：用户/付费/活跃数据"""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.updated_at >= thirty_days_ago).count()
    paid_users = db.query(User).filter(User.subscription_tier != "free").count()

    # 今日新增
    today_new = db.query(User).filter(User.created_at >= today_start).count()

    # 订阅分布
    free_count = db.query(User).filter(User.subscription_tier == "free").count()
    basic_count = db.query(User).filter(User.subscription_tier == "basic").count()
    pro_count = db.query(User).filter(User.subscription_tier == "pro").count()

    # 宠物/客户/销售汇总
    total_pets = db.query(Pet).filter(Pet.is_deleted == False).count()
    total_buyer_leads = db.query(BuyerLead).filter(BuyerLead.is_deleted == False).count()
    total_sales_amount = db.query(func.sum(PetSale.sale_price)).filter(PetSale.is_deleted == False).scalar() or 0

    return {
        "code": 0,
        "data": {
            "users": {
                "total": total_users,
                "active_30d": active_users,
                "today_new": today_new,
                "paid": paid_users,
            },
            "subscription_distribution": {
                "free": free_count,
                "basic": basic_count,
                "pro": pro_count,
            },
            "content": {
                "total_pets": total_pets,
                "total_buyer_leads": total_buyer_leads,
                "total_sales_amount": total_sales_amount / 100,  # 分转元
            },
        }
    }

@router.get("/users", dependencies=[Depends(require_admin)])
async def admin_users(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """用户列表（管理视角）"""
    total = db.query(User).count()
    users = db.query(User).order_by(User.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()

    result = []
    for u in users:
        pet_count = db.query(Pet).filter(Pet.owner_id == u.id, Pet.is_deleted == False).count()
        result.append({
            "id": u.id,
            "nickname": u.nickname,
            "phone": u.phone,
            "kennel_name": u.kennel_name,
            "subscription_tier": u.subscription_tier,
            "subscription_expire": u.subscription_expire.isoformat() if u.subscription_expire else None,
            "pet_count": pet_count,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return {"code": 0, "data": {"list": result, "total": total, "page": page, "page_size": page_size}}

@router.get("/subscriptions", dependencies=[Depends(require_admin)])
async def admin_subscriptions(db: Session = Depends(get_db)):
    """订阅付费概览"""
    paid_orders = db.query(SubscriptionOrder).filter(SubscriptionOrder.status == "paid").order_by(SubscriptionOrder.created_at.desc()).limit(50).all()

    total_revenue = db.query(func.sum(SubscriptionOrder.price)).filter(SubscriptionOrder.status == "paid").scalar() or 0

    return {
        "code": 0,
        "data": {
            "total_revenue": total_revenue / 100,
            "recent_orders": [{
                "id": o.id,
                "user_id": o.user_id,
                "tier": o.tier,
                "price": o.price / 100,
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            } for o in paid_orders[:20]],
        }
    }

@router.get("/verification-codes", dependencies=[Depends(require_admin)])
async def admin_vcodes(page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    """最近验证码记录（用于调试短信问题）"""
    total = db.query(VerificationCode).count()
    codes = db.query(VerificationCode).order_by(VerificationCode.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {
        "code": 0,
        "data": {
            "list": [{
                "id": c.id,
                "phone": c.phone,
                "code": c.code,
                "is_used": c.is_used,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            } for c in codes],
            "total": total,
        }
    }
