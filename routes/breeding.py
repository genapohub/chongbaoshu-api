from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime, date, timedelta
from config.database import get_db
from models.breeding_record import BreedingRecord
from models.litter import Litter
from models.pet import Pet
from middleware.auth import get_current_user, TokenData
from utils.helpers import format_datetime, calculate_due_date, is_valid_status_transition
from utils.sanitize import sanitize_string
from config.error_codes import Errors

router = APIRouter(prefix="/api/breeding", tags=["breeding"])


class AddBreedingRequest(BaseModel):
    pet_id: Optional[int] = None
    mother_pet_id: Optional[int] = None
    father_id: Optional[int] = None
    mate_name: Optional[str] = None
    mating_date: str
    mating_method: Optional[str] = "natural"
    due_date: Optional[str] = None
    fee: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    litter_count: Optional[int] = None
    delivery_date: Optional[str] = None


class UpdateBreedingRequest(BaseModel):
    mate_name: Optional[str] = None
    mating_date: Optional[str] = None
    mating_method: Optional[str] = None
    due_date: Optional[str] = None
    fee: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    litter_count: Optional[int] = None
    delivery_date: Optional[str] = None


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
        query = query.filter(or_(BreedingRecord.mother_id == pet_id, BreedingRecord.father_id == pet_id))
    if status:
        query = query.filter(BreedingRecord.status == status)

    total = query.count()
    records = query.order_by(BreedingRecord.mate_date.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # Batch preload parents to avoid N+1 queries
    parent_ids = set()
    for record in records:
        if record.mother_id:
            parent_ids.add(record.mother_id)
        if record.father_id:
            parent_ids.add(record.father_id)

    parents_map = {}
    if parent_ids:
        parent_records = db.query(Pet).filter(Pet.id.in_(parent_ids)).all()
        for p in parent_records:
            parents_map[p.id] = p

    result = []
    for record in records:
        mother = parents_map.get(record.mother_id)
        father = parents_map.get(record.father_id) if record.father_id else None
        result.append({
            "id": record.id,
            "pet_id": record.mother_id,
            "mother_id": record.mother_id,
            "mother_name": mother.name if mother else None,
            "father_id": record.father_id,
            "father_name": father.name if father else (record.father_name or record.mate_name),
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
    # 支持两种字段名：pet_id 和 mother_pet_id
    pet_id = request.pet_id if request.pet_id is not None else request.mother_pet_id
    
    if pet_id is None:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="缺少宠物ID")
    
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.is_deleted == False
    ).first()
    if not pet:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="宠物不存在")

    due_date = request.due_date or calculate_due_date(pet.species, request.mating_date)

    breeding = BreedingRecord(
        owner_id=current_user.id,
        mother_id=pet_id,
        father_id=request.father_id,
        mate_name=sanitize_string(request.mate_name) if request.mate_name else None,
        mate_date=datetime.strptime(request.mating_date, "%Y-%m-%d").date(),
        due_date=datetime.strptime(due_date, "%Y-%m-%d").date() if due_date else None,
        mating_method=request.mating_method or "natural",
        fee=request.fee,
        notes=sanitize_string(request.notes) if request.notes else None,
        status="mated",
    )
    db.add(breeding)
    db.commit()

    # 产仔登记时自动创建同窝记录
    if request.status == "delivered" and request.litter_count and request.litter_count > 0:
        litter = Litter(
            user_id=current_user.id,
            mother_id=breeding.mother_id,
            father_id=breeding.father_id,
            breeding_record_id=breeding.id,
            birth_date=request.delivery_date if request.delivery_date else datetime.utcnow().date(),
            litter_size=request.litter_count,
        )
        db.add(litter)
        db.flush()
        # 批量创建幼犬
        for i in range(1, request.litter_count + 1):
            puppy = Pet(
                owner_id=current_user.id,
                name=f"幼犬{i}",
                species="犬",
                birth_date=litter.birth_date,
                litter_id=litter.id,
                role="幼崽",
                status="active",
                is_for_sale=True,
            )
            db.add(puppy)
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
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="繁育记录不存在")

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
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="繁育记录不存在")

    if request.mate_name is not None:
        record.mate_name = sanitize_string(request.mate_name) if request.mate_name else None
    if request.mating_date is not None:
        record.mate_date = datetime.strptime(request.mating_date, "%Y-%m-%d").date()
        if request.due_date is None:
            pet = db.query(Pet).filter(Pet.id == record.mother_id).first()
            if pet:
                due_date_str = calculate_due_date(pet.species, request.mating_date)
                record.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    if request.due_date is not None:
        record.due_date = datetime.strptime(request.due_date, "%Y-%m-%d").date()
    if request.mating_method is not None:
        record.mating_method = request.mating_method
    if request.fee is not None:
        record.fee = request.fee
    if request.status is not None:
        record.status = request.status
    if request.notes is not None:
        record.notes = sanitize_string(request.notes) if request.notes else None
    if request.litter_count is not None:
        record.litter_count = request.litter_count
    if request.delivery_date is not None:
        record.delivery_date = datetime.strptime(request.delivery_date, "%Y-%m-%d").date()

    db.commit()

    # 产仔登记时自动创建同窝记录
    if request.status == "delivered" and request.litter_count and request.litter_count > 0:
        litter = Litter(
            user_id=current_user.id,
            mother_id=record.mother_id,
            father_id=record.father_id,
            breeding_record_id=record.id,
            birth_date=request.delivery_date if request.delivery_date else datetime.utcnow().date(),
            litter_size=request.litter_count,
        )
        db.add(litter)
        db.flush()
        # 批量创建幼犬
        for i in range(1, request.litter_count + 1):
            puppy = Pet(
                owner_id=current_user.id,
                name=f"幼犬{i}",
                species="犬",
                birth_date=litter.birth_date,
                litter_id=litter.id,
                role="幼崽",
                status="active",
                is_for_sale=True,
            )
            db.add(puppy)
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
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="繁育记录不存在")

    # Validate status transition
    if not is_valid_status_transition(record.status, status):
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail=f"无效的状态变更：{record.status} → {status}")

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
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="繁育记录不存在")

    record.is_deleted = True
    db.commit()

    return {"code": 0, "message": "删除成功"}


class CheckInbreedingRequest(BaseModel):
    mother_pet_id: int
    father_pet_id: int


@router.post("/check-inbreeding")
async def check_inbreeding(
    request: CheckInbreedingRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    检测两只宠物是否有近亲关系
    """
    mother = db.query(Pet).filter(
        Pet.id == request.mother_pet_id,
        Pet.owner_id == current_user.id,
        Pet.is_deleted == False
    ).first()
    if not mother:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="母宠不存在")

    father = db.query(Pet).filter(
        Pet.id == request.father_pet_id,
        Pet.owner_id == current_user.id,
        Pet.is_deleted == False
    ).first()
    if not father:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="父宠不存在")

    def get_pedigree(pet):
        """获取宠物的祖先信息"""
        pedigree = set()
        if pet.name:
            pedigree.add(pet.name)
        if pet.father_name:
            pedigree.add(pet.father_name)
        if pet.mother_name:
            pedigree.add(pet.mother_name)
        if pet.grandfather_p_name:
            pedigree.add(pet.grandfather_p_name)
        if pet.grandmother_p_name:
            pedigree.add(pet.grandmother_p_name)
        if pet.grandfather_m_name:
            pedigree.add(pet.grandfather_m_name)
        if pet.grandmother_m_name:
            pedigree.add(pet.grandmother_m_name)
        return pedigree

    def get_parent_ids(pet):
        """获取宠物的父母ID"""
        parent_ids = set()
        if pet.father_id:
            parent_ids.add(pet.father_id)
        if pet.mother_id:
            parent_ids.add(pet.mother_id)
        return parent_ids

    # 检查ID关系
    mother_parent_ids = get_parent_ids(mother)
    father_parent_ids = get_parent_ids(father)

    # 检查是否有共同的祖先ID
    common_parent_ids = mother_parent_ids & father_parent_ids
    if common_parent_ids:
        return {
            "code": 0,
            "data": {
                "is_inbreeding": True,
                "relation": "父母辈近亲",
                "message": "检测到两只宠物有共同的父母，建议不要配对"
            }
        }

    # 检查是否互为父母
    if mother.father_id == father.id or mother.mother_id == father.id:
        return {
            "code": 0,
            "data": {
                "is_inbreeding": True,
                "relation": "父女/母子关系",
                "message": "检测到近亲关系，建议不要配对"
            }
        }

    if father.father_id == mother.id or father.mother_id == mother.id:
        return {
            "code": 0,
            "data": {
                "is_inbreeding": True,
                "relation": "父女/母子关系",
                "message": "检测到近亲关系，建议不要配对"
            }
        }

    # 检查名字关系
    mother_pedigree = get_pedigree(mother)
    father_pedigree = get_pedigree(father)
    common_names = mother_pedigree & father_pedigree
    if common_names:
        return {
            "code": 0,
            "data": {
                "is_inbreeding": True,
                "relation": "家族成员重叠",
                "message": f"检测到共同祖先: {', '.join(common_names)}，建议不要配对"
            }
        }

    return {
        "code": 0,
        "data": {
            "is_inbreeding": False,
            "relation": "无近亲关系",
            "message": "未检测到近亲关系，可以安全配对"
        }
    }
