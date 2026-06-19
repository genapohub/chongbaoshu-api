"""
微信模板消息 & 短信通知推送工具
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from config.env import is_production

push_logger = logging.getLogger("push")

# ── 微信模板消息 ────────────────────────────────────────

# 模板ID（需在微信公众平台申请）
TEMPLATE_IDS = {
    "vaccine": os.getenv("WX_TEMPLATE_VACCINE", ""),   # 疫苗提醒
    "deworm": os.getenv("WX_TEMPLATE_DEWORM", ""),      # 驱虫提醒
    "due_date": os.getenv("WX_TEMPLATE_DUE", ""),       # 预产期提醒
    "announce": os.getenv("WX_TEMPLATE_ANNOUNCE", ""),   # 公告通知
}

WX_APP_ID = os.getenv("WX_APP_ID", "")
WX_APP_SECRET = os.getenv("WX_APP_SECRET", "")

# 内存缓存 access_token
_cached_token = None
_cached_token_expires = None


def _get_access_token() -> str:
    """获取微信 access_token（带缓存）"""
    global _cached_token, _cached_token_expires
    now = datetime.utcnow()

    if _cached_token and _cached_token_expires and now < _cached_token_expires:
        return _cached_token

    url = "https://api.weixin.qq.com/cgi-bin/token"
    resp = requests.get(url, params={
        "grant_type": "client_credential",
        "appid": WX_APP_ID,
        "secret": WX_APP_SECRET,
    }, timeout=10)
    data = resp.json()

    if "access_token" not in data:
        push_logger.error("获取 access_token 失败: %s", data)
        raise Exception(f"微信 access_token 获取失败: {data.get('errmsg', '')}")

    _cached_token = data["access_token"]
    _cached_token_expires = now + timedelta(seconds=data.get("expires_in", 7200) - 300)
    return _cached_token


def send_template_message(openid: str, template_id: str, data: dict, page: str = "") -> bool:
    """发送微信模板消息"""
    if not is_production() or not template_id:
        push_logger.info("[DEV] 模板消息跳过发送: openid=%s template=%s data=%s", openid, template_id, json.dumps(data, ensure_ascii=False))
        return True  # 开发模式静默成功

    try:
        token = _get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}"
        payload = {
            "touser": openid,
            "template_id": template_id,
            "page": page,
            "data": data,
        }
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()

        if result.get("errcode") != 0:
            push_logger.error("模板消息发送失败: openid=%s err=%s", openid, result)
            return False

        push_logger.info("模板消息已发送: openid=%s template=%s", openid, template_id)
        return True

    except Exception as e:
        push_logger.error("模板消息发送异常: %s", e)
        return False


def send_reminder_push(db: Session) -> dict:
    """扫描待办提醒，向用户推送模板消息。返回统计 dict"""
    from models.user import User
    from models.pet import Pet
    from models.health_record import HealthRecord
    from models.breeding_record import BreedingRecord

    count = {"vaccine": 0, "deworm": 0, "due_date": 0, "skipped": 0}

    now = datetime.utcnow()
    cutoff = now + timedelta(days=7)

    # 扫描已开启提醒且未取消订阅的用户
    users = db.query(User).filter(
        User.is_active == True,
        User.subscription_tier != "free",
    ).all()

    for user in users:
        openid = user.openid
        if not openid:
            continue

        # 疫苗提醒
        if user.remind_vaccine and TEMPLATE_IDS.get("vaccine"):
            upcoming = db.query(HealthRecord).join(Pet).filter(
                Pet.owner_id == user.id,
                HealthRecord.type == "vaccine",
                HealthRecord.next_date >= now.date(),
                HealthRecord.next_date <= cutoff.date(),
                HealthRecord.is_deleted == False,
            ).first()
            if upcoming:
                pet = db.query(Pet).filter(Pet.id == upcoming.pet_id).first()
                ok = send_template_message(openid, TEMPLATE_IDS["vaccine"], {
                    "thing1": {"value": pet.name if pet else "未知"},
                    "thing2": {"value": upcoming.vaccine_type or "疫苗"},
                    "date3": {"value": upcoming.next_date.strftime("%Y-%m-%d") if upcoming.next_date else ""},
                    "thing4": {"value": "请及时安排接种"},
                })
                if ok:
                    count["vaccine"] += 1

        # 驱虫提醒
        if user.remind_deworm and TEMPLATE_IDS.get("deworm"):
            upcoming = db.query(HealthRecord).join(Pet).filter(
                Pet.owner_id == user.id,
                HealthRecord.type == "deworm",
                HealthRecord.next_date >= now.date(),
                HealthRecord.next_date <= cutoff.date(),
                HealthRecord.is_deleted == False,
            ).first()
            if upcoming:
                pet = db.query(Pet).filter(Pet.id == upcoming.pet_id).first()
                ok = send_template_message(openid, TEMPLATE_IDS["deworm"], {
                    "thing1": {"value": pet.name if pet else "未知"},
                    "thing2": {"value": upcoming.deworm_type or "驱虫"},
                    "date3": {"value": upcoming.next_date.strftime("%Y-%m-%d") if upcoming.next_date else ""},
                    "thing4": {"value": "请及时安排驱虫"},
                })
                if ok:
                    count["deworm"] += 1

        # 预产期提醒
        if user.remind_due and TEMPLATE_IDS.get("due_date"):
            # 只提醒非Pro用户？不限。按 pre-due 日期推送
            upcoming = db.query(BreedingRecord).filter(
                BreedingRecord.owner_id == user.id,
                BreedingRecord.due_date >= now.date(),
                BreedingRecord.due_date <= cutoff.date(),
                BreedingRecord.is_deleted == False,
                BreedingRecord.status != "delivered",
            ).order_by(BreedingRecord.due_date).first()
            if upcoming:
                pet = db.query(Pet).filter(Pet.id == upcoming.mother_id).first()
                ok = send_template_message(openid, TEMPLATE_IDS["due_date"], {
                    "thing1": {"value": pet.name if pet else "未知"},
                    "date2": {"value": upcoming.due_date.strftime("%Y-%m-%d") if upcoming.due_date else ""},
                    "thing3": {"value": f"预计{days_left}天后分娩" if (days_left := (upcoming.due_date - now.date()).days) > 0 else "已到预产期"},
                    "thing4": {"value": "请提前准备产房"},
                })
                if ok:
                    count["due_date"] += 1

    return count
