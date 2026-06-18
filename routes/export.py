from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from config.database import get_db
from models.user import User
from models.pet import Pet
from models.export_task import ExportTask
from config.error_codes import Errors
from middleware.auth import get_current_user, TokenData
from utils.helpers import get_effective_tier

router = APIRouter(prefix="/api/export", tags=["export"])

class CreateExportTaskRequest(BaseModel):
    type: str

@router.get("/tasks")
async def get_export_tasks(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tasks = db.query(ExportTask).filter(
        ExportTask.user_id == current_user.id
    ).order_by(ExportTask.created_at.desc()).limit(10).all()
    
    result = []
    for task in tasks:
        result.append({
            "id": task.id,
            "type": task.type,
            "status": task.status,
            "file_path": task.file_path,
            "created_at": task.created_at,
            "completed_at": task.completed_at,
        })
    
    return {
        "code": 0,
        "data": result
    }

@router.post("/tasks")
async def create_export_task(
    request: CreateExportTaskRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if get_effective_tier(user) != "pro":
        raise HTTPException(status_code=403, detail="数据导出仅Pro用户可用")
    
    valid_types = ["pets", "breeding", "health", "all"]
    if request.type not in valid_types:
        raise HTTPException(status_code=1001, detail=f"导出类型必须是: {'/'.join(valid_types)}")
    
    task = ExportTask(
        user_id=current_user.id,
        type=request.type,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {
        "code": 0,
        "message": "导出任务已创建",
        "data": {
            "id": task.id,
            "type": task.type,
            "status": task.status,
            "created_at": task.created_at,
        }
    }
