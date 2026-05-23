from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from config.database import get_db
from models.health_record import HealthRecord
from models.pet import Pet
from middleware.auth import get_current_user, TokenData
from utils.helpers import calculate_next_date

router = APIRouter(prefix="/api/health", tags=["health"])

class AddHealthRequest(BaseModel):
    pet_id: int
    type: str
    vaccine_type: Optional[str] = None
    deworm_type: Optional[str] = None
    medicine_name: Optional[str] = None
    dosage: Optional[str] = None
    batch_no: Optional[str] = None
    vaccine_round: Optional[int] = None
    vet_hospital: Optional[str] = None
    record_date: str
    notes: Optional[str] = None

class UpdateHealthRequest(BaseModel):
    type: Optional[str] = None
    vaccine_type: Optional[str] = None
    deworm_type: Optional[str] = None
    medicine_name: Optional[str] = None
    dosage: Optional[str] = None
    batch_no: Optional[str] = None
    vaccine_round: Optional[int] = None
    vet_hospital: Optional[str] = None
    record_date: Optional[str] = None
    next_date: Optional[str] = None
    notes: Optional[str] = None

@router.get("")
async def get_health_records(
    pet_id: Optional[int] = None,
    type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(HealthRecord).filter(HealthRecord.owner_id == current_user.id, HealthRecord.is_deleted == False)
    
    if pet_id:
        query = query.filter(HealthRecord.pet_id == pet_id)
    if type:
        query = query.filter(HealthRecord.type == type)
    
    total = query.count()
    records = query.order_by(HealthRecord.record_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    result = []
    for record in records:
        pet = db.query(Pet).filter(Pet.id == record.pet_id).first()
        result.append({
            "id": record.id,
            "pet_id": record.pet_id,
            "pet_name": pet.name if pet else None,
            "type": record.type,
            "vaccine_type": record.vaccine_type,
            "deworm_type": record.deworm_type,
            "medicine_name": record.medicine_name,
            "dosage": record.dosage,
            "batch_no": record.batch_no,
            "vaccine_round": record.vaccine_round,
            "vet_hospital": record.vet_hospital,
            "record_date": record.record_date,
            "next_date": record.next_date,
            "notes": record.notes,
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

@router.get("/reminders")
async def get_reminders(
    days: int = Query(7, description="提醒天数范围"),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    today = datetime.now().date()
    end_date = today + timedelta(days=days)
    
    health_records = db.query(HealthRecord).filter(
        HealthRecord.owner_id == current_user.id,
        HealthRecord.is_deleted == False,
        HealthRecord.next_date != None,
        HealthRecord.next_date <= end_date,
    ).order_by(HealthRecord.next_date).all()
    
    return {
        "code": 0,
        "data": {
            "healthReminders": [
                {
                    "id": r.id,
                    "pet_id": r.pet_id,
                    "type": r.type,
                    "vaccine_type": r.vaccine_type,
                    "record_date": r.record_date,
                    "next_date": r.next_date,
                }
                for r in health_records
            ],
            "dueReminders": [],
        }
    }

@router.post("")
async def add_health_record(
    request: AddHealthRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pet = db.query(Pet).filter(Pet.id == request.pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=1001, detail="宠物不存在")
    
    record_date_obj = datetime.strptime(request.record_date, "%Y-%m-%d").date()
    next_date = calculate_next_date(request.type, request.record_date, request.vaccine_type, request.deworm_type)
    next_date_obj = datetime.strptime(next_date, "%Y-%m-%d").date() if next_date else None
    
    health = HealthRecord(
        pet_id=request.pet_id,
        owner_id=current_user.id,
        type=request.type,
        vaccine_type=request.vaccine_type,
        deworm_type=request.deworm_type,
        medicine_name=request.medicine_name,
        dosage=request.dosage,
        batch_no=request.batch_no,
        vaccine_round=request.vaccine_round,
        vet_hospital=request.vet_hospital,
        record_date=record_date_obj,
        next_date=next_date_obj,
        notes=request.notes,
    )
    db.add(health)
    db.commit()
    db.refresh(health)
    
    return {
        "code": 0,
        "message": "添加成功",
        "data": {
            "id": health.id,
            "pet_id": health.pet_id,
            "type": health.type,
            "record_date": health.record_date,
            "next_date": health.next_date,
        }
    }

@router.put("/{record_id}")
async def update_health_record(
    record_id: int,
    request: UpdateHealthRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(HealthRecord).filter(HealthRecord.id == record_id, HealthRecord.owner_id == current_user.id, HealthRecord.is_deleted == False).first()
    if not record:
        raise HTTPException(status_code=1001, detail="健康记录不存在")
    
    if request.type is not None:
        record.type = request.type
    if request.vaccine_type is not None:
        record.vaccine_type = request.vaccine_type
    if request.deworm_type is not None:
        record.deworm_type = request.deworm_type
    if request.medicine_name is not None:
        record.medicine_name = request.medicine_name
    if request.dosage is not None:
        record.dosage = request.dosage
    if request.batch_no is not None:
        record.batch_no = request.batch_no
    if request.vaccine_round is not None:
        record.vaccine_round = request.vaccine_round
    if request.vet_hospital is not None:
        record.vet_hospital = request.vet_hospital
    if request.record_date is not None:
        record.record_date = datetime.strptime(request.record_date, "%Y-%m-%d").date()
        next_date = calculate_next_date(record.type, request.record_date, record.vaccine_type, record.deworm_type)
        record.next_date = datetime.strptime(next_date, "%Y-%m-%d").date() if next_date else None
    if request.next_date is not None:
        record.next_date = datetime.strptime(request.next_date, "%Y-%m-%d").date()
    if request.notes is not None:
        record.notes = request.notes
    
    db.commit()
    db.refresh(record)
    
    return {
        "code": 0,
        "message": "更新成功",
        "data": {
            "id": record.id,
            "type": record.type,
            "record_date": record.record_date,
            "next_date": record.next_date,
        }
    }

@router.delete("/{record_id}")
async def delete_health_record(
    record_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(HealthRecord).filter(HealthRecord.id == record_id, HealthRecord.owner_id == current_user.id, HealthRecord.is_deleted == False).first()
    if not record:
        raise HTTPException(status_code=1001, detail="健康记录不存在")
    
    record.is_deleted = True
    db.commit()
    
    return {"code": 0, "message": "删除成功"}
