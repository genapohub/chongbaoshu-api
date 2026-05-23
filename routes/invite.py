import random
import string
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from config.database import get_db
from models.user import User
from middleware.auth import get_current_user, TokenData
from utils.helpers import format_datetime

router = APIRouter(prefix="/api/invite", tags=["invite"])

def generate_invite_code(db: Session, length: int = 8) -> str:
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    while True:
        code = ''.join(random.choice(chars) for _ in range(length))
        if db.query(User).filter(User.invite_code == code).count() == 0:
            return code

class RedeemCodeRequest(BaseModel):
    code: str

@router.get("/code")
async def get_my_invite_code(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if not user.invite_code:
        user.invite_code = generate_invite_code(db)
        db.commit()
    
    return {
        "code": 0,
        "data": {
            "invite_code": user.invite_code,
        }
    }

@router.post("/redeem")
async def redeem_invite_code(
    request: RedeemCodeRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not request.code:
        raise HTTPException(status_code=400, detail="邀请码不能为空")
    
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    inviter = db.query(User).filter(User.invite_code == request.code.upper()).first()
    if not inviter:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    
    if inviter.id == user.id:
        raise HTTPException(status_code=400, detail="不能兑换自己的邀请码")
    
    from models.invite_record import InviteRecord
    
    existing = db.query(InviteRecord).filter(InviteRecord.invitee_id == user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="已被邀请过，不能重复兑换")
    
    from datetime import datetime, timedelta
    # 使用本地时间避免时区问题
    now = datetime.now()
    expire_time = now + timedelta(days=7)
    
    invite_record = InviteRecord(
        inviter_id=inviter.id,
        invitee_id=user.id,
        invite_code=request.code.upper(),
        status="redeemed",
        reward_days=7,
        redeemed_at=now,
    )
    db.add(invite_record)
    
    # 设置被邀请人的Pro会员
    user.subscription_tier = "pro"
    user.subscription_source = "reward"
    if user.subscription_expire:
        # 统一转换为时间戳比较，避免时区问题
        expire_ts = user.subscription_expire.timestamp() if hasattr(user.subscription_expire, 'timestamp') else user.subscription_expire
        now_ts = now.timestamp()
        if expire_ts > now_ts:
            # 如果已有到期时间且在未来，在原有基础上延长7天
            user.subscription_expire = user.subscription_expire + timedelta(days=7)
        else:
            # 已过期或为None，设置为当前时间+7天
            user.subscription_expire = expire_time
    else:
        # 没有到期时间，设置为当前时间+7天
        user.subscription_expire = expire_time
    
    # 设置邀请人的Pro会员奖励（邀请人也获得7天）
    inviter.subscription_tier = "pro"
    inviter.subscription_source = "reward"
    if inviter.subscription_expire:
        # 统一转换为时间戳比较，避免时区问题
        expire_ts = inviter.subscription_expire.timestamp() if hasattr(inviter.subscription_expire, 'timestamp') else inviter.subscription_expire
        now_ts = now.timestamp()
        if expire_ts > now_ts:
            # 如果已有到期时间且在未来，在原有基础上延长7天
            inviter.subscription_expire = inviter.subscription_expire + timedelta(days=7)
        else:
            # 已过期或为None，设置为当前时间+7天
            inviter.subscription_expire = expire_time
    else:
        # 没有到期时间，设置为当前时间+7天
        inviter.subscription_expire = expire_time
    
    db.commit()
    
    return {
        "code": 0,
        "message": "兑换成功，获得7天Pro体验",
        "data": {
            "reward_days": 7,
        }
    }

@router.get("/records")
async def get_invite_records(
    page: int = 1,
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from models.invite_record import InviteRecord
    query = db.query(InviteRecord).filter(InviteRecord.inviter_id == current_user.id)
    
    total = query.count()
    records = query.order_by(InviteRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    result = []
    for record in records:
        invitee = db.query(User).filter(User.id == record.invitee_id).first()
        result.append({
            "id": record.id,
            "invitee_nickname": invitee.nickname if invitee else "未知用户",
            "invitee_avatar": invitee.avatar_url if invitee else None,
            "invitee_created_at": format_datetime(invitee.created_at) if invitee else None,
            "invite_code": record.invite_code,
            "reward_days": record.reward_days,
            "status": record.status,
            "redeemed_at": format_datetime(record.redeemed_at),
            "created_at": format_datetime(record.created_at),
        })
    
    return {
        "code": 0,
        "data": {
            "total": total,
            "page": page,
            "pageSize": page_size,
            "list": result,
        }
    }

@router.get("/stats")
async def get_invite_stats(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from models.invite_record import InviteRecord
    total_invites = db.query(InviteRecord).filter(InviteRecord.inviter_id == current_user.id).count()
    redeemed_invites = db.query(InviteRecord).filter(
        InviteRecord.inviter_id == current_user.id,
        InviteRecord.status.in_(["redeemed", "rewarded"])
    ).count()
    
    total_reward_days = total_invites * 7
    
    return {
        "code": 0,
        "data": {
            "total_invites": total_invites,
            "redeemed_invites": redeemed_invites,
            "rewarded_invites": total_invites,
            "total_reward_days": total_reward_days,
            "inviteCount": total_invites,
        }
    }
