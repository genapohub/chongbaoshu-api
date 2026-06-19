from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from config.database import get_db
from models.litter import Litter
from models.pet import Pet
from config.error_codes import Errors
from middleware.auth import get_current_user, TokenData
from utils.sanitize import sanitize_string

router = APIRouter(prefix="/api/litters", tags=["litters"])

class CreateLitterRequest(BaseModel):
    mother_id: int
    father_id: Optional[int] = None
    breeding_record_id: Optional[int] = None
    birth_date: str
    litter_size: int = 0
    notes: Optional[str] = None

@router.get("")
async def list_litters(
    page: int = 1,
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = db.query(Litter).filter(Litter.user_id == current_user.id)
    total = q.count()
    litters = q.order_by(Litter.birth_date.desc()).offset((page-1)*page_size).limit(page_size).all()

    result = []
    for lit in litters:
        mother_name = None
        father_name = None
        if lit.mother_id:
            m = db.query(Pet).filter(Pet.id == lit.mother_id).first()
            mother_name = m.name if m else None
        if lit.father_id:
            f = db.query(Pet).filter(Pet.id == lit.father_id).first()
            father_name = f.name if f else None

        # count puppies
        puppy_count = db.query(Pet).filter(Pet.litter_id == lit.id, Pet.is_deleted == False).count()

        result.append({
            "id": lit.id,
            "mother_id": lit.mother_id,
            "mother_name": mother_name,
            "father_id": lit.father_id,
            "father_name": father_name,
            "birth_date": lit.birth_date.strftime("%Y-%m-%d") if lit.birth_date else None,
            "litter_size": lit.litter_size,
            "puppy_count": puppy_count,
            "notes": lit.notes,
            "created_at": lit.created_at.isoformat() if lit.created_at else None,
        })
    return {"code": 0, "data": {"list": result, "total": total, "page": page, "page_size": page_size}}

@router.post("")
async def create_litter(
    req: CreateLitterRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 校验母犬属于当前用户
    mother = db.query(Pet).filter(Pet.id == req.mother_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not mother:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="母犬不存在")

    litter = Litter(
        user_id=current_user.id,
        mother_id=req.mother_id,
        father_id=req.father_id,
        breeding_record_id=req.breeding_record_id,
        birth_date=datetime.strptime(req.birth_date, "%Y-%m-%d").date(),
        litter_size=req.litter_size,
        notes=sanitize_string(req.notes.strip()) if req.notes else None,
    )
    db.add(litter)
    db.commit()
    db.refresh(litter)
    return {"code": 0, "data": {"id": litter.id}, "message": "同窝记录已创建"}

@router.get("/{litter_id}")
async def get_litter(
    litter_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lit = db.query(Litter).filter(Litter.id == litter_id, Litter.user_id == current_user.id).first()
    if not lit:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="同窝记录不存在")

    # 获取同窝幼犬
    puppies = db.query(Pet).filter(Pet.litter_id == lit.id, Pet.is_deleted == False).all()
    puppy_list = [{"id": p.id, "name": p.name, "breed": p.breed, "gender": p.gender, "status": p.status, "price": p.price} for p in puppies]

    mother_name = None
    father_name = None
    if lit.mother_id:
        m = db.query(Pet).filter(Pet.id == lit.mother_id).first()
        mother_name = m.name if m else None
    if lit.father_id:
        f = db.query(Pet).filter(Pet.id == lit.father_id).first()
        father_name = f.name if f else None

    return {
        "code": 0,
        "data": {
            "id": lit.id,
            "mother_id": lit.mother_id,
            "mother_name": mother_name,
            "father_id": lit.father_id,
            "father_name": father_name,
            "birth_date": lit.birth_date.strftime("%Y-%m-%d") if lit.birth_date else None,
            "litter_size": lit.litter_size,
            "notes": lit.notes,
            "puppies": puppy_list,
        }
    }

@router.post("/{litter_id}/puppies/batch")
async def batch_add_puppies(
    litter_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """为同窝批量添加幼犬（使用默认名称 幼犬1, 幼犬2...）"""
    lit = db.query(Litter).filter(Litter.id == litter_id, Litter.user_id == current_user.id).first()
    if not lit:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="同窝记录不存在")

    existing = db.query(Pet).filter(Pet.litter_id == lit.id, Pet.is_deleted == False).count()
    if existing >= lit.litter_size:
        return {"code": 0, "message": "同窝幼犬已全部登记"}

    created = 0
    for i in range(existing + 1, lit.litter_size + 1):
        pet = Pet(
            owner_id=current_user.id,
            name=f"幼犬{i}",
            species="犬",
            breed=None,
            gender=None,
            birth_date=lit.birth_date,
            litter_id=lit.id,
            role="幼崽",
            status="active",
            is_for_sale=True,
        )
        db.add(pet)
        created += 1

    db.commit()
    return {"code": 0, "message": f"已批量添加 {created} 只幼犬"}
