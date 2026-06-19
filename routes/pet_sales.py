from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from config.database import get_db
from models.pet_sale import PetSale
from models.pet import Pet
from models.buyer_lead import BuyerLead
from config.error_codes import Errors
from middleware.auth import get_current_user, TokenData
from utils.sanitize import sanitize_string

router = APIRouter(prefix="/api/pet-sales", tags=["pet_sales"])

class CreateSaleRequest(BaseModel):
    pet_id: int
    buyer_name: str
    sale_price: int  # 分
    sale_date: str  # ISO日期
    buyer_lead_id: Optional[int] = None
    items_included: Optional[str] = None
    notes: Optional[str] = None

@router.get("")
async def list_sales(
    page: int = 1,
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = db.query(PetSale).filter(
        PetSale.user_id == current_user.id,
        PetSale.is_deleted == False
    )
    total = q.count()
    sales = q.order_by(PetSale.sale_date.desc()).offset((page-1)*page_size).limit(page_size).all()

    result = []
    for s in sales:
        pet_name = None
        if s.pet_id:
            pet = db.query(Pet).filter(Pet.id == s.pet_id).first()
            pet_name = pet.name if pet else None
        result.append({
            "id": s.id,
            "pet_id": s.pet_id,
            "pet_name": pet_name,
            "buyer_name": s.buyer_name,
            "sale_price": s.sale_price,
            "sale_date": s.sale_date.strftime("%Y-%m-%d") if s.sale_date else None,
            "items_included": s.items_included,
            "notes": s.notes,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return {"code": 0, "data": {"list": result, "total": total, "page": page, "page_size": page_size}}

@router.post("")
async def create_sale(
    req: CreateSaleRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 校验宠物属于当前用户
    pet = db.query(Pet).filter(
        Pet.id == req.pet_id,
        Pet.owner_id == current_user.id,
        Pet.is_deleted == False
    ).first()
    if not pet:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="宠物不存在")

    sale = PetSale(
        user_id=current_user.id,
        pet_id=req.pet_id,
        buyer_lead_id=req.buyer_lead_id,
        buyer_name=sanitize_string(req.buyer_name.strip()),
        sale_price=req.sale_price,
        sale_date=datetime.strptime(req.sale_date, "%Y-%m-%d"),
        items_included=sanitize_string(req.items_included.strip()) if req.items_included else None,
        notes=sanitize_string(req.notes.strip()) if req.notes else None,
    )
    db.add(sale)

    # 宠物标记为已售
    pet.status = "sold"
    pet.is_for_sale = False

    # 如果关联了意向客户，更新状态
    if req.buyer_lead_id:
        lead = db.query(BuyerLead).filter(BuyerLead.id == req.buyer_lead_id, BuyerLead.user_id == current_user.id).first()
        if lead:
            lead.status = "sold"
            lead.last_followed_at = datetime.utcnow()

    db.commit()
    db.refresh(sale)
    return {"code": 0, "data": {"id": sale.id}, "message": "销售记录已创建，宠物已标记为已售"}

@router.get("/summary")
async def sales_summary(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """本月销售汇总"""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sales = db.query(PetSale).filter(
        PetSale.user_id == current_user.id,
        PetSale.is_deleted == False,
        PetSale.sale_date >= month_start.date()
    ).all()

    total_revenue = sum(s.sale_price for s in sales)
    sale_count = len(sales)
    # 本月均价
    avg_price = total_revenue // sale_count if sale_count > 0 else 0

    return {
        "code": 0,
        "data": {
            "month": now.strftime("%Y-%m"),
            "sale_count": sale_count,
            "total_revenue": total_revenue / 100,  # 分转元
            "avg_price": avg_price / 100,
        }
    }

@router.delete("/{sale_id}")
async def delete_sale(
    sale_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sale = db.query(PetSale).filter(
        PetSale.id == sale_id,
        PetSale.user_id == current_user.id,
        PetSale.is_deleted == False
    ).first()
    if not sale:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="销售记录不存在")
    sale.is_deleted = True
    db.commit()
    return {"code": 0, "message": "已删除"}
