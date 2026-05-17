from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from config.database import SessionLocal
from models.notification import Notification
from middleware.auth import get_current_user, TokenData

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("")
async def get_notifications(
    type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if type:
        query = query.filter(Notification.type == type)

    total = query.count()
    records = query.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for record in records:
        result.append({
            "id": record.id,
            "type": record.type,
            "title": record.title,
            "content": record.content,
            "data": record.data,
            "is_read": record.is_read,
            "created_at": record.created_at,
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

@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    notification.is_read = True
    db.commit()

    return {"code": 0, "message": "标记成功"}

@router.put("/read-all")
async def mark_all_notifications_read(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()

    return {"code": 0, "message": "全部标记已读"}

@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()

    return {
        "code": 0,
        "data": {
            "count": count,
        }
    }
