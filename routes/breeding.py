from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timedelta
from config.database import SessionLocal
from models.breeding_record import BreedingRecord
from models.pet import Pet
from middleware.auth import get_current_user, TokenData

router = APIRouter(prefix="/api/breeding", tags=["breeding"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def format_datetime(dt):
    """格式化datetime为字符串"""
    if dt:
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(dt, date):
            return dt.strftime("%Y-%m-%d")
    return None


def calculate_due_date(species: str, mating_date: str) -> str:
    """根据物种和配种日期计算预产期"""
    try:
        m_date = datetime.strptime(mating_date, "%Y-%m-%d").date()
    except:
        return None

    gestation_days = {
        "dog": 63,
        "cat": 65,
        "rabbit": 30,
        "bird": 21,
    }
    days = gestation_days.get(species, 63)
    due = m_date + timedelta(days=days)
    return due.strftime("%Y-%m-%d")


class AddBreedingRequest(BaseModel):
    pet_id: int
    mate_name: Optional[str] = None
    mating_date: str
    mating_method: Optional[str] = "natural"
    due_date: Optional[str] = None
    fee: Optional[float] = None
    notes: Optional[str] = None


class UpdateBreedingRequest(BaseModel):
    mate_name: Optional[str] = None
    mating_date: Optional[str] = None
    mating_method: Optional[str] = None
    due_date: Optional[str] = None
    fee: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def get_breeding_records(
    pet_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(BreedingRecord).filter(
        BreedingRecord.owner_id == current_user.id,
        BreedingRecord.is_deleted == False
    )

    if pet_id:
        query = query.filter(BreedingRecord.mother_id == pet_id)
    if status:
        query = query.filter(BreedingRecord.status == status)

    total = query.count()
    records = query.order_by(BreedingRecord.mate_date.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for record in records:
        mother = db.query(Pet).filter(Pet.id == record.mother_id).first()
        result.append({
            "id": record.id,
            "pet_id": record.mother_id,
            "pet_name": mother.name if mother else None,
            "mate_name": record.mate_name,
            "mating_date": format_datetime(record.mate_date),
            "due_date": format_datetime(record.due_date),
            "mating_method": record.mating_method,
            "fee": record.fee,
            "status": record.status,
            "notes": record.notes,
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


@router.post("")
async def add_breeding_record(
    request: AddBreedingRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pet = db.query(Pet).filter(
        Pet.id == request.pet_id,
        Pet.owner_id == current_user.id,
        Pet.is_deleted == False
    ).first()
    if not pet:
        raise HTTPException(status_code=1001, detail="宠物不存在")

    due_date = request.due_date or calculate_due_date(pet.species, request.mating_date)

    breeding = BreedingRecord(
        owner_id=current_user.id,
        mother_id=request.pet_id,
        mate_name=request.mate_name,
        mate_date=datetime.strptime(request.mating_date, "%Y-%m-%d").date(),
        due_date=datetime.strptime(due_date, "%Y-%m-%d").date() if due_date else None,
        mating_method=request.mating_method or "natural",
        fee=request.fee,
        notes=request.notes,
        status="mated",
    )
    db.add(breeding)
    db.commit()
    db.refresh(breeding)

    return {
        "code": 0,
        "message": "添加成功",
        "data": {
            "id": breeding.id,
            "pet_id": breeding.mother_id,
            "mating_date": format_datetime(breeding.mate_date),
            "due_date": format_datetime(breeding.due_date),
        }
    }


@router.get("/{record_id}")
async def get_breeding_record(
    record_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(BreedingRecord).filter(
        BreedingRecord.id == record_id,
        BreedingRecord.owner_id == current_user.id,
        BreedingRecord.is_deleted == False
    ).first()
    if not record:
        raise HTTPException(status_code=1001, detail="繁育记录不存在")

    mother = db.query(Pet).filter(Pet.id == record.mother_id).first()

    return {
        "code": 0,
        "data": {
            "id": record.id,
            "pet_id": record.mother_id,
            "pet_name": mother.name if mother else None,
            "mate_name": record.mate_name,
            "mating_date": format_datetime(record.mate_date),
            "due_date": format_datetime(record.due_date),
            "mating_method": record.mating_method,
            "fee": record.fee,
            "status": record.status,
            "notes": record.notes,
            "litter_count": record.litter_count,
            "ultrasound_date": format_datetime(record.ultrasound_date),
            "delivery_date": format_datetime(record.delivery_date),
            "created_at": format_datetime(record.created_at),
        }
    }


@router.put("/{record_id}")
async def update_breeding_record(
    record_id: int,
    request: UpdateBreedingRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(BreedingRecord).filter(
        BreedingRecord.id == record_id,
        BreedingRecord.owner_id == current_user.id,
        BreedingRecord.is_deleted == False
    ).first()
    if not record:
        raise HTTPException(status_code=1001, detail="繁育记录不存在")

    if request.mate_name is not None:
        record.mate_name = request.mate_name
    if request.mating_date is not None:
        record.mate_date = datetime.strptime(request.mating_date, "%Y-%m-%d").date()
        if request.due_date is None:
            pet = db.query(Pet).filter(Pet.id == record.mother_id).first()
            if pet:
                record.due_date = datetime.strptime(calculate_due_date(pet.species, request.mating_date), "%Y-%m-%d").date()
    if request.due_date is not None:
        record.due_date = datetime.strptime(request.due_date, "%Y-%m-%d").date()
    if request.mating_method is not None:
        record.mating_method = request.mating_method
    if request.fee is not None:
        record.fee = request.fee
    if request.status is not None:
        record.status = request.status
    if request.notes is not None:
        record.notes = request.notes

    db.commit()
    db.refresh(record)

    return {
        "code": 0,
        "message": "更新成功",
        "data": {
            "id": record.id,
            "status": record.status,
        }
    }


@router.put("/{record_id}/status")
async def update_breeding_status(
    record_id: int,
    status: str = Body(..., embed=True),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(BreedingRecord).filter(
        BreedingRecord.id == record_id,
        BreedingRecord.owner_id == current_user.id,
        BreedingRecord.is_deleted == False
    ).first()
    if not record:
        raise HTTPException(status_code=1001, detail="繁育记录不存在")

    record.status = status
    db.commit()

    return {
        "code": 0,
        "message": "状态更新成功",
        "data": {
            "id": record.id,
            "status": record.status,
        }
    }


@router.delete("/{record_id}")
async def delete_breeding_record(
    record_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(BreedingRecord).filter(
        BreedingRecord.id == record_id,
        BreedingRecord.owner_id == current_user.id,
        BreedingRecord.is_deleted == False
    ).first()
    if not record:
        raise HTTPException(status_code=1001, detail="繁育记录不存在")

    record.is_deleted = True
    db.commit()

    return {"code": 0, "message": "删除成功"}
