from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from routes.auth import get_current_user, TokenData
from config.database import get_db
from sqlalchemy.orm import Session
from models.feedback import Feedback
from config.error_codes import Errors
from utils.sanitize import sanitize_string

router = APIRouter()

class FeedbackRequest(BaseModel):
    content: str
    contact: Optional[str] = None

@router.post("")
@router.post("/")
async def create_feedback(
    request: FeedbackRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not request.content or len(request.content.strip()) < 10:
        raise HTTPException(status_code=400, detail="反馈内容至少需要10个字符")
    
    feedback = Feedback(
        user_id=current_user.id,
        content=sanitize_string(request.content.strip()),
        contact=sanitize_string(request.contact.strip()) if request.contact else None
    )
    db.add(feedback)
    db.commit()
    
    return {
        "code": 0,
        "message": "反馈提交成功，感谢您的宝贵意见！"
    }