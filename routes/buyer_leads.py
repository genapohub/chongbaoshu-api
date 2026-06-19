from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from config.database import get_db
from models.buyer_lead import BuyerLead
from models.pet import Pet
from config.error_codes import Errors
from middleware.auth import get_current_user, TokenData
from utils.sanitize import sanitize_string

router = APIRouter(prefix="/api/buyer-leads", tags=["buyer_leads"])

class CreateBuyerLeadRequest(BaseModel):
    pet_id: Optional[int] = None
    buyer_name: str
    buyer_wechat: Optional[str] = None
    buyer_phone: Optional[str] = None
    budget: Optional[str] = None
    notes: Optional[str] = None

class UpdateBuyerLeadRequest(BaseModel):
    pet_id: Optional[int] = None
    buyer_name: Optional[str] = None
    buyer_wechat: Optional[str] = None
    buyer_phone: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[str] = None
    notes: Optional[str] = None

@router.get("")
async def list_buyer_leads(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = db.query(BuyerLead).filter(
        BuyerLead.user_id == current_user.id,
        BuyerLead.is_deleted == False
    )
    if status:
        q = q.filter(BuyerLead.status == status)
    total = q.count()
    leads = q.order_by(BuyerLead.updated_at.desc()).offset((page-1)*page_size).limit(page_size).all()

    result = []
    for lead in leads:
        pet_name = None
        if lead.pet_id:
            pet = db.query(Pet).filter(Pet.id == lead.pet_id).first()
            pet_name = pet.name if pet else None
        result.append({
            "id": lead.id,
            "pet_id": lead.pet_id,
            "pet_name": pet_name,
            "buyer_name": lead.buyer_name,
            "buyer_wechat": lead.buyer_wechat,
            "buyer_phone": lead.buyer_phone,
            "status": lead.status,
            "budget": lead.budget,
            "notes": lead.notes,
            "last_followed_at": lead.last_followed_at.isoformat() if lead.last_followed_at else None,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        })
    return {"code": 0, "data": {"list": result, "total": total, "page": page, "page_size": page_size}}

@router.post("")
async def create_buyer_lead(
    req: CreateBuyerLeadRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lead = BuyerLead(
        user_id=current_user.id,
        pet_id=req.pet_id,
        buyer_name=sanitize_string(req.buyer_name.strip()),
        buyer_wechat=sanitize_string(req.buyer_wechat.strip()) if req.buyer_wechat else None,
        buyer_phone=sanitize_string(req.buyer_phone.strip()) if req.buyer_phone else None,
        status="consulting",
        budget=sanitize_string(req.budget.strip()) if req.budget else None,
        notes=sanitize_string(req.notes.strip()) if req.notes else None,
        last_followed_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return {"code": 0, "data": {"id": lead.id}, "message": "意向客户已添加"}

@router.put("/{lead_id}")
async def update_buyer_lead(
    lead_id: int,
    req: UpdateBuyerLeadRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lead = db.query(BuyerLead).filter(
        BuyerLead.id == lead_id,
        BuyerLead.user_id == current_user.id,
        BuyerLead.is_deleted == False
    ).first()
    if not lead:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="意向客户不存在")

    if req.buyer_name is not None:
        lead.buyer_name = sanitize_string(req.buyer_name.strip())
    if req.buyer_wechat is not None:
        lead.buyer_wechat = sanitize_string(req.buyer_wechat.strip())
    if req.buyer_phone is not None:
        lead.buyer_phone = sanitize_string(req.buyer_phone.strip())
    if req.status is not None:
        valid_statuses = ["consulting", "visited", "negotiating", "sold", "lost"]
        if req.status not in valid_statuses:
            raise HTTPException(status_code=Errors.PARAM_INVALID, detail=f"状态值无效，可选: {', '.join(valid_statuses)}")
        lead.status = req.status
    if req.budget is not None:
        lead.budget = sanitize_string(req.budget.strip())
    if req.notes is not None:
        lead.notes = sanitize_string(req.notes.strip())
    if req.pet_id is not None:
        lead.pet_id = req.pet_id

    lead.last_followed_at = datetime.utcnow()
    db.commit()
    return {"code": 0, "message": "已更新"}

@router.put("/{lead_id}/follow")
async def follow_buyer_lead(
    lead_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """快速标记跟进时间"""
    lead = db.query(BuyerLead).filter(
        BuyerLead.id == lead_id,
        BuyerLead.user_id == current_user.id,
        BuyerLead.is_deleted == False
    ).first()
    if not lead:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="意向客户不存在")
    lead.last_followed_at = datetime.utcnow()
    db.commit()
    return {"code": 0, "message": "已记录跟进"}

@router.delete("/{lead_id}")
async def delete_buyer_lead(
    lead_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lead = db.query(BuyerLead).filter(
        BuyerLead.id == lead_id,
        BuyerLead.user_id == current_user.id,
        BuyerLead.is_deleted == False
    ).first()
    if not lead:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="意向客户不存在")
    lead.is_deleted = True
    db.commit()
    return {"code": 0, "message": "已删除"}
