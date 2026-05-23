import os
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from config.database import get_db
from models.user import User
from models.pet import Pet
from models.breeding_record import BreedingRecord
from models.health_record import HealthRecord
from models.subscription import Subscription
from models.verification_code import VerificationCode
from middleware.auth import create_access_token, get_current_user, TokenData
from utils.helpers import get_user_limits, format_datetime

router = APIRouter(prefix="/api/auth", tags=["auth"])

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
async def wx_login(request: WxLoginRequest, db: Session = Depends(get_db)):
    if not request.code:
        raise HTTPException(status_code=1001, detail="缺少微信登录code")
    
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
            result = code2session(request.code)
            openid = result["openid"]
            unionid = result.get("unionid")
            user, is_new = get_or_create_user(db, openid, unionid)
        
        access_token = create_access_token({
            "id": user.id,
            "openid": user.openid,
            "subscription_tier": user.subscription_tier,
        })
        
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
                    "subscription_tier": user.subscription_tier,
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profile")
async def get_profile(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
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
            "subscription_tier": user.subscription_tier,
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
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if nickname is not None:
        user.nickname = nickname
    if avatar_url is not None:
        user.avatar_url = avatar_url
    if phone is not None:
        user.phone = phone
    if kennel_name is not None:
        user.kennel_name = kennel_name
    if kennel_address is not None:
        user.kennel_address = kennel_address
    if kennel_intro is not None:
        user.kennel_intro = kennel_intro
    if main_breeds is not None:
        user.main_breeds = main_breeds
    if wechat is not None:
        user.wechat = wechat
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
        import os
        from uuid import uuid4
        
        upload_dir = "uploads/kennel"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_ext = kennel_logo.filename.split(".")[-1] if "." in kennel_logo.filename else "jpg"
        file_name = f"{uuid4().hex}.{file_ext}"
        file_path = f"{upload_dir}/{file_name}"
        
        with open(file_path, "wb") as f:
            f.write(await kennel_logo.read())
        
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
            "subscription_tier": user.subscription_tier,
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
    
    limits = get_user_limits(user.subscription_tier)
    
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
    
    return {
        "code": 0,
        "data": {
            "user": {
                "id": user.id,
                "nickname": user.nickname or "用户",
                "avatar_url": user.avatar_url,
                "subscription_tier": user.subscription_tier,
            },
            "stats": {
                "petCount": pet_count,
                "breedingCount": breeding_count,
                "healthCount": health_count,
            },
            "limits": limits,
            "upcomingReminders": upcoming_reminders,
            "dueBreedings": due_breedings,
        }
    }

@router.get("/limits")
async def get_limits(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    limits = get_user_limits(user.subscription_tier)
    
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
            "tier": user.subscription_tier,
            "maxPets": get_limit_value(limits["maxPets"]),
            "maxBreedingRecords": get_limit_value(limits.get("maxBreedingRecords", limits.get("maxBreedings", 3))),
            "currentPets": current_pets,
            "limits": processed_limits,
        }
    }

@router.post("/send-code")
async def send_verification_code(
    request: SendCodeRequest,
    db: Session = Depends(get_db)
):
    if not request.phone or len(request.phone) != 11:
        raise HTTPException(status_code=1001, detail="请输入正确的手机号")
    
    if DEV_MODE:
        code = "123456"  # 开发环境固定验证码
        print(f"[DEV MODE] 验证码: {code}")
    else:
        import random
        code = f"{random.randint(100000, 999999)}"
        # TODO: 接入短信服务商发送验证码
    
    verification = VerificationCode(
        phone=request.phone,
        code=code,
    )
    db.add(verification)
    db.commit()
    
    return {
        "code": 0,
        "message": "验证码已发送"
    }

@router.post("/phone-login")
async def phone_login(request: PhoneLoginRequest, db: Session = Depends(get_db)):
    if not request.phone or not request.code:
        raise HTTPException(status_code=1001, detail="请输入手机号和验证码")
    
    # 开发模式：支持默认验证码123456直接登录（无需先发送验证码）
    if DEV_MODE and request.code == "123456":
        print(f"[DEV MODE] 使用默认验证码登录: {request.phone}")
        user, is_new = get_or_create_user(db, f"phone_{request.phone}", None)
        
        if not user.phone:
            user.phone = request.phone
            db.commit()
            db.refresh(user)
        
        access_token = create_access_token({
            "id": user.id,
            "openid": user.openid,
            "subscription_tier": user.subscription_tier,
        })
        
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
                    "subscription_tier": user.subscription_tier,
                },
                "isNew": is_new,
            }
        }
    
    # 生产模式：正常验证码校验
    verification = db.query(VerificationCode).filter(
        VerificationCode.phone == request.phone,
        VerificationCode.code == request.code,
        VerificationCode.is_used == False
    ).order_by(VerificationCode.created_at.desc()).first()
    
    if not verification:
        raise HTTPException(status_code=1001, detail="验证码错误或已失效")
    
    if (datetime.now() - verification.created_at).total_seconds() > 300:
        raise HTTPException(status_code=1001, detail="验证码已过期")
    
    verification.is_used = True
    db.commit()
    
    user, is_new = get_or_create_user(db, f"phone_{request.phone}", None)
    
    if not user.phone:
        user.phone = request.phone
        db.commit()
        db.refresh(user)
    
    access_token = create_access_token({
        "id": user.id,
        "openid": user.openid,
        "subscription_tier": user.subscription_tier,
    })
    
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
                "subscription_tier": user.subscription_tier,
            },
            "isNew": is_new,
        }
    }
