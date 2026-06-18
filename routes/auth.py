import os
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import sentry_sdk
from config.database import get_db
from models.user import User
from models.pet import Pet
from models.breeding_record import BreedingRecord
from models.health_record import HealthRecord
from models.subscription import Subscription
from models.verification_code import VerificationCode
from config.error_codes import Errors
from middleware.auth import create_access_token, get_current_user, TokenData
from utils.helpers import get_user_limits, format_datetime, get_effective_tier
from utils.sanitize import sanitize_string
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── 限流器（auth 路由专用） ────────────────────────────────
_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

ENV = os.getenv("ENV", "development")
WX_APP_ID = os.getenv("WX_APP_ID", "")
WX_APP_SECRET = os.getenv("WX_APP_SECRET", "")

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"  # 通过环境变量控制，生产环境勿设为 true
DEV_OPENID = os.getenv("DEV_OPENID", "dev_default_user")

class WxLoginRequest(BaseModel):
    code: str

class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    kennel_name: Optional[str] = None
    kennel_address: Optional[str] = None
    kennel_intro: Optional[str] = None
    kennel_logo: Optional[str] = None
    main_breeds: Optional[str] = None
    wechat: Optional[str] = None
    remind_vaccine: Optional[bool] = None
    remind_deworm: Optional[bool] = None
    remind_due: Optional[bool] = None
    remind_vaccine_days: Optional[int] = None
    remind_deworm_days: Optional[int] = None
    remind_due_days: Optional[int] = None
    notify_in_app: Optional[bool] = None
    notify_wechat: Optional[bool] = None


class SendCodeRequest(BaseModel):
    phone: str


class PhoneLoginRequest(BaseModel):
    phone: str
    code: str

def get_or_create_user(db: Session, openid: str, unionid: Optional[str] = None):
    user = db.query(User).filter(User.openid == openid).first()
    is_new = False
    
    if not user:
        user = User(
            openid=openid,
            unionid=unionid,
            subscription_tier="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        subscription = Subscription(
            user_id=user.id,
            tier="free",
            status="active",
        )
        db.add(subscription)
        db.commit()
        is_new = True
    
    return user, is_new

@router.post("/wx-login")
@_limiter.limit("10/minute")
async def wx_login(request: Request, req: WxLoginRequest, db: Session = Depends(get_db)):
    # Sentry：设置登录流程 tags
    sentry_sdk.set_tag("flow", "login")
    sentry_sdk.set_tag("login_method", "wx")

    if not req.code:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="缺少微信登录code")

    try:
        if DEV_MODE:
            # 开发模式：使用固定openid，保持用户数据持久化
            user, is_new = get_or_create_user(db, DEV_OPENID, None)

            if not user.nickname:
                user.nickname = "开发者"
                db.commit()
                db.refresh(user)

            print(f"[DEV MODE] 模拟登录: {DEV_OPENID}, is_new={is_new}")
        else:
            # 生产模式：调用真实微信API
            from utils.wechat import code2session
            result = code2session(req.code)
            openid = result["openid"]
            unionid = result.get("unionid")
            user, is_new = get_or_create_user(db, openid, unionid)
        
        # get_effective_tier 在登录时计算一次放入 token，后续请求直接读 TokenData.subscription_tier
        effective_tier = get_effective_tier(user)
        access_token = create_access_token({
            "id": user.id,
            "openid": user.openid,
            "subscription_tier": effective_tier,
        })
        
        # Sentry：设置用户上下文和订阅等级标签
        sentry_sdk.set_user({"id": str(user.id), "openid": user.openid or ""})
        sentry_sdk.set_tag("subscription_tier", get_effective_tier(user))
        
        return {
            "code": 0,
            "message": "登录成功",
            "data": {
                "token": access_token,
                "user": {
                    "id": user.id,
                    "nickname": user.nickname,
                    "avatar_url": user.avatar_url,
                    "phone": user.phone,
                    "kennel_name": user.kennel_name,
                    "subscription_tier": get_effective_tier(user),
                },
                "isNew": is_new,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 登录失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=Errors.SERVER_ERROR, detail=str(e))

@router.get("/profile")
async def get_profile(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="用户不存在")
    
    return {
        "code": 0,
        "data": {
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "phone": user.phone,
            "kennel_name": user.kennel_name,
            "kennel_address": user.kennel_address,
            "kennel_intro": user.kennel_intro,
            "kennel_logo": user.kennel_logo,
            "main_breeds": user.main_breeds,
            "wechat": user.wechat,
            "subscription_tier": get_effective_tier(user),
            "subscription_expire": format_datetime(user.subscription_expire),
            "subscription_source": user.subscription_source,
            "invite_code": user.invite_code,
            "remind_vaccine": user.remind_vaccine,
            "remind_deworm": user.remind_deworm,
            "remind_due": user.remind_due,
            "remind_vaccine_days": user.remind_vaccine_days,
            "remind_deworm_days": user.remind_deworm_days,
            "remind_due_days": user.remind_due_days,
            "notify_in_app": user.notify_in_app,
            "notify_wechat": user.notify_wechat,
            "created_at": format_datetime(user.created_at),
        }
    }

@router.put("/profile")
@router.post("/profile")
async def update_profile(
    nickname: Optional[str] = Form(None),
    avatar_url: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    kennel_name: Optional[str] = Form(None),
    kennel_address: Optional[str] = Form(None),
    kennel_intro: Optional[str] = Form(None),
    main_breeds: Optional[str] = Form(None),
    wechat: Optional[str] = Form(None),
    remind_vaccine: Optional[bool] = Form(None),
    remind_deworm: Optional[bool] = Form(None),
    remind_due: Optional[bool] = Form(None),
    remind_vaccine_days: Optional[int] = Form(None),
    remind_deworm_days: Optional[int] = Form(None),
    remind_due_days: Optional[int] = Form(None),
    notify_in_app: Optional[bool] = Form(None),
    notify_wechat: Optional[bool] = Form(None),
    kennel_logo: Optional[UploadFile] = File(None),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="用户不存在")
    
    if nickname is not None:
        user.nickname = sanitize_string(nickname)
    if avatar_url is not None:
        user.avatar_url = avatar_url
    if phone is not None:
        user.phone = phone
    if kennel_name is not None:
        user.kennel_name = sanitize_string(kennel_name)
    if kennel_address is not None:
        user.kennel_address = sanitize_string(kennel_address)
    if kennel_intro is not None:
        user.kennel_intro = sanitize_string(kennel_intro)
    if main_breeds is not None:
        user.main_breeds = sanitize_string(main_breeds)
    if wechat is not None:
        user.wechat = sanitize_string(wechat)
    if remind_vaccine is not None:
        user.remind_vaccine = remind_vaccine
    if remind_deworm is not None:
        user.remind_deworm = remind_deworm
    if remind_due is not None:
        user.remind_due = remind_due
    if remind_vaccine_days is not None:
        user.remind_vaccine_days = remind_vaccine_days
    if remind_deworm_days is not None:
        user.remind_deworm_days = remind_deworm_days
    if remind_due_days is not None:
        user.remind_due_days = remind_due_days
    if notify_in_app is not None:
        user.notify_in_app = notify_in_app
    if notify_wechat is not None:
        user.notify_wechat = notify_wechat
    
    if kennel_logo is not None:
        from middleware.upload import validate_file, MAX_FILE_SIZE
        
        validate_file(kennel_logo)
        
        content = await kennel_logo.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=Errors.PARAM_INVALID, detail="犬舍Logo文件大小超过限制（最大5MB）")
        
        import os
        from uuid import uuid4
        from pathlib import Path
        
        upload_dir = "uploads/kennel"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_ext = Path(kennel_logo.filename).suffix.lower() if kennel_logo.filename else ".jpg"
        file_name = f"{uuid4().hex}{file_ext}"
        file_path = f"{upload_dir}/{file_name}"
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        user.kennel_logo = f"/{file_path}"
    
    db.commit()
    
    return {
        "code": 0,
        "message": "更新成功",
        "data": {
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "phone": user.phone,
            "kennel_name": user.kennel_name,
            "kennel_address": user.kennel_address,
            "kennel_intro": user.kennel_intro,
            "kennel_logo": user.kennel_logo,
            "main_breeds": user.main_breeds,
            "wechat": user.wechat,
            "subscription_tier": get_effective_tier(user),
            "remind_vaccine": user.remind_vaccine,
            "remind_deworm": user.remind_deworm,
            "remind_due": user.remind_due,
            "remind_vaccine_days": user.remind_vaccine_days,
            "remind_deworm_days": user.remind_deworm_days,
            "remind_due_days": user.remind_due_days,
            "notify_in_app": user.notify_in_app,
            "notify_wechat": user.notify_wechat,
        }
    }

@router.get("/dashboard")
async def get_dashboard(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    
    pet_count = db.query(Pet).filter(Pet.owner_id == current_user.id, Pet.is_deleted == False).count()
    breeding_count = db.query(BreedingRecord).filter(BreedingRecord.owner_id == current_user.id, BreedingRecord.is_deleted == False).count()
    health_count = db.query(HealthRecord).filter(HealthRecord.owner_id == current_user.id).count()
    
    limits = get_user_limits(get_effective_tier(user))
    
    # 获取健康提醒数据
    upcoming_reminders = []
    health_records = db.query(HealthRecord).filter(
        HealthRecord.owner_id == current_user.id,
        HealthRecord.is_deleted == False,
        HealthRecord.next_date != None
    ).limit(10).all()
    
    for record in health_records:
        pet = db.query(Pet).filter(Pet.id == record.pet_id, Pet.is_deleted == False).first()
        upcoming_reminders.append({
            "id": record.id,
            "pet_name": pet.name if pet else "宠物",
            "type": record.type,
            "vaccine_type": record.vaccine_type,
            "next_date": format_datetime(record.next_date) if record.next_date else None,
        })
    
    # 获取预产期提醒
    due_breedings = []
    breedings = db.query(BreedingRecord).filter(
        BreedingRecord.owner_id == current_user.id,
        BreedingRecord.is_deleted == False,
        BreedingRecord.due_date != None
    ).limit(10).all()
    
    for breeding in breedings:
        mother_pet = db.query(Pet).filter(Pet.id == breeding.mother_id, Pet.is_deleted == False).first()
        due_breedings.append({
            "id": breeding.id,
            "mother_name": mother_pet.name if mother_pet else "母犬",
            "due_date": format_datetime(breeding.due_date) if breeding.due_date else None,
        })
    
    # 获取最近动态
    recent_activities = []

    # 最近添加/更新的宠物
    recent_pets = db.query(Pet).filter(
        Pet.owner_id == current_user.id,
        Pet.is_deleted == False
    ).order_by(Pet.updated_at.desc()).limit(5).all()

    for pet in recent_pets:
        action = "添加了宠物" if pet.created_at == pet.updated_at else "更新了宠物"
        recent_activities.append({
            "text": f"{action}「{pet.name}」",
            "time": format_datetime(pet.updated_at),
            "sort_time": pet.updated_at,
        })

    # 最近添加的健康记录
    recent_health = db.query(HealthRecord).filter(
        HealthRecord.owner_id == current_user.id,
        HealthRecord.is_deleted == False
    ).order_by(HealthRecord.created_at.desc()).limit(5).all()

    for record in recent_health:
        pet = db.query(Pet).filter(Pet.id == record.pet_id, Pet.is_deleted == False).first()
        pet_name = pet.name if pet else "宠物"
        type_labels = {"vaccine": "疫苗", "deworm": "驱虫", "other": "健康"}
        type_label = type_labels.get(record.type, "健康")
        recent_activities.append({
            "text": f"为「{pet_name}」添加了{type_label}记录",
            "time": format_datetime(record.created_at),
            "sort_time": record.created_at,
        })

    # 最近添加的繁育记录
    recent_breedings = db.query(BreedingRecord).filter(
        BreedingRecord.owner_id == current_user.id,
        BreedingRecord.is_deleted == False
    ).order_by(BreedingRecord.created_at.desc()).limit(5).all()

    for breeding in recent_breedings:
        mother_pet = db.query(Pet).filter(Pet.id == breeding.mother_id, Pet.is_deleted == False).first()
        mother_name = mother_pet.name if mother_pet else "母犬"
        recent_activities.append({
            "text": f"为「{mother_name}」添加了配种记录",
            "time": format_datetime(breeding.created_at),
            "sort_time": breeding.created_at,
        })

    # 按时间倒序排列，取最近10条
    recent_activities.sort(key=lambda x: x["sort_time"] if x["sort_time"] else datetime.min, reverse=True)
    recent_activities = recent_activities[:10]

    # 移除排序用的临时字段
    for act in recent_activities:
        act.pop("sort_time", None)

    return {
        "code": 0,
        "data": {
            "user": {
                "id": user.id,
                "nickname": user.nickname or "用户",
                "avatar_url": user.avatar_url,
                "subscription_tier": get_effective_tier(user),
            },
            "stats": {
                "petCount": pet_count,
                "breedingCount": breeding_count,
                "healthCount": health_count,
            },
            "limits": limits,
            "upcomingReminders": upcoming_reminders,
            "dueBreedings": due_breedings,
            "recentActivities": recent_activities,
        }
    }

@router.get("/limits")
async def get_limits(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=Errors.UNAUTHORIZED, detail="用户不存在")
    
    limits = get_user_limits(get_effective_tier(user))
    
    current_pets = db.query(Pet).filter(Pet.owner_id == current_user.id, Pet.is_deleted == False).count()
    
    # 处理unlimited值，使用一个很大的数字代替
    def get_limit_value(value):
        if value == "unlimited":
            return 999999
        return value
    
    # 创建一个处理后的limits副本
    processed_limits = {}
    for key, value in limits.items():
        processed_limits[key] = get_limit_value(value)
    
    return {
        "code": 0,
        "data": {
            "tier": get_effective_tier(user),
            "maxPets": get_limit_value(limits["maxPets"]),
            "maxBreedingRecords": get_limit_value(limits.get("maxBreedingRecords", limits.get("maxBreedings", 3))),
            "currentPets": current_pets,
            "limits": processed_limits,
        }
    }

@router.post("/send-code")
@_limiter.limit("1/minute")
async def send_verification_code(
    request: Request, req: SendCodeRequest, db: Session = Depends(get_db)
):
    if not req.phone or len(req.phone) != 11:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="请输入正确的手机号")

    if DEV_MODE:
        code = "123456"  # 开发环境固定验证码
        print(f"[DEV MODE] 验证码: {code}")
    else:
        import random
        code = f"{random.randint(100000, 999999)}"
        # TODO: 接入短信服务商发送验证码
    
    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    verification = VerificationCode(
        phone=req.phone,
        code=code,
        expires_at=expires_at,
    )
    db.add(verification)
    db.commit()
    
    return {
        "code": 0,
        "message": "验证码已发送"
    }

@router.post("/phone-login")
@_limiter.limit("10/minute")
async def phone_login(request: Request, req: PhoneLoginRequest, db: Session = Depends(get_db)):
    # Sentry：设置登录流程 tags
    sentry_sdk.set_tag("flow", "login")
    sentry_sdk.set_tag("login_method", "phone")

    if not req.phone or not req.code:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="请输入手机号和验证码")

    # 暴力破解防护：检查最近5分钟内失败次数
    from datetime import timedelta as _td
    five_min_ago = datetime.utcnow() - _td(minutes=5)
    failed_count = db.query(VerificationCode).filter(
        VerificationCode.phone == req.phone,
        VerificationCode.is_used == False,
        VerificationCode.created_at >= five_min_ago,
    ).count()
    if failed_count >= 5:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="验证码错误次数过多，请5分钟后重试")

    # 开发模式：支持默认验证码123456直接登录（无需先发送验证码）
    if DEV_MODE and req.code == "123456":
        print(f"[DEV MODE] 使用默认验证码登录: {req.phone}")
        user, is_new = get_or_create_user(db, f"phone_{req.phone}", None)

        if not user.phone:
            user.phone = req.phone
            db.commit()
            db.refresh(user)
        
        # get_effective_tier 在登录时计算一次放入 token，后续请求直接读 TokenData.subscription_tier
        effective_tier = get_effective_tier(user)
        access_token = create_access_token({
            "id": user.id,
            "openid": user.openid,
            "subscription_tier": effective_tier,
        })
        
        # Sentry：设置用户上下文和订阅等级标签
        sentry_sdk.set_user({"id": str(user.id), "openid": user.openid or ""})
        sentry_sdk.set_tag("subscription_tier", get_effective_tier(user))
        
        return {
            "code": 0,
            "message": "登录成功",
            "data": {
                "token": access_token,
                "user": {
                    "id": user.id,
                    "nickname": user.nickname,
                    "avatar_url": user.avatar_url,
                    "phone": user.phone,
                    "kennel_name": user.kennel_name,
                    "subscription_tier": get_effective_tier(user),
                },
                "isNew": is_new,
            }
        }
    
    # 生产模式：正常验证码校验
    verification = db.query(VerificationCode).filter(
        VerificationCode.phone == req.phone,
        VerificationCode.code == req.code,
        VerificationCode.is_used == False
    ).order_by(VerificationCode.created_at.desc()).first()

    if not verification:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="验证码错误或已失效")

    if (datetime.utcnow() - verification.created_at).total_seconds() > 300:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="验证码已过期")

    verification.is_used = True
    db.commit()

    user, is_new = get_or_create_user(db, f"phone_{req.phone}", None)

    if not user.phone:
        user.phone = req.phone
        db.commit()
        db.refresh(user)
    
    access_token = create_access_token({
        "id": user.id,
        "openid": user.openid,
        "subscription_tier": get_effective_tier(user),
    })
    
    # Sentry：设置用户上下文和订阅等级标签
    sentry_sdk.set_user({"id": str(user.id), "openid": user.openid or ""})
    sentry_sdk.set_tag("subscription_tier", get_effective_tier(user))
    
    return {
        "code": 0,
        "message": "登录成功",
        "data": {
            "token": access_token,
            "user": {
                "id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "phone": user.phone,
                "kennel_name": user.kennel_name,
                "subscription_tier": get_effective_tier(user),
            },
            "isNew": is_new,
        }
    }
