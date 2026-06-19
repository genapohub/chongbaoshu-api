from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from config.database import get_db
from models.ledger import LedgerEntry
from config.error_codes import Errors
from middleware.auth import get_current_user, TokenData
from utils.sanitize import sanitize_string

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

CATEGORIES = {
    "income": ["销售", "寄养", "配种服务", "其他收入"],
    "expense": ["配种费", "疫苗药品", "狗粮", "寄养费", "兽医", "用品", "其他支出"],
}

class CreateLedgerRequest(BaseModel):
    entry_type: str  # income or expense
    category: str
    amount: int  # 分
    entry_date: str
    description: Optional[str] = None

@router.get("/categories")
async def get_categories():
    return {"code": 0, "data": CATEGORIES}

@router.get("")
async def list_entries(
    entry_type: Optional[str] = None,
    month: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = db.query(LedgerEntry).filter(LedgerEntry.user_id == current_user.id)
    if entry_type:
        q = q.filter(LedgerEntry.entry_type == entry_type)
    if month:
        start = datetime.strptime(month, "%Y-%m")
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        q = q.filter(LedgerEntry.entry_date >= start, LedgerEntry.entry_date < end)
    total = q.count()
    entries = q.order_by(LedgerEntry.entry_date.desc()).offset((page-1)*page_size).limit(page_size).all()

    result = []
    for e in entries:
        result.append({
            "id": e.id,
            "entry_type": e.entry_type,
            "category": e.category,
            "amount": e.amount,
            "entry_date": e.entry_date.strftime("%Y-%m-%d") if e.entry_date else None,
            "description": e.description,
        })
    return {"code": 0, "data": {"list": result, "total": total, "page": page, "page_size": page_size}}

@router.get("/summary")
async def ledger_summary(
    month: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """收支汇总"""
    if not month:
        month = datetime.utcnow().strftime("%Y-%m")

    start = datetime.strptime(month, "%Y-%m")
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)

    q = db.query(LedgerEntry).filter(
        LedgerEntry.user_id == current_user.id,
        LedgerEntry.entry_date >= start,
        LedgerEntry.entry_date < end
    )

    income_total = 0
    expense_total = 0
    for e in q.all():
        if e.entry_type == "income":
            income_total += e.amount
        else:
            expense_total += e.amount

    return {
        "code": 0,
        "data": {
            "month": month,
            "income_total": income_total / 100,
            "expense_total": expense_total / 100,
            "net": (income_total - expense_total) / 100,
        }
    }

@router.post("")
async def create_entry(
    req: CreateLedgerRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.entry_type not in ("income", "expense"):
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="类型必须是 income 或 expense")
    if req.amount <= 0:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="金额必须大于0")

    entry = LedgerEntry(
        user_id=current_user.id,
        entry_type=req.entry_type,
        category=sanitize_string(req.category.strip()),
        amount=req.amount,
        entry_date=datetime.strptime(req.entry_date, "%Y-%m-%d"),
        description=sanitize_string(req.description.strip()) if req.description else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"code": 0, "data": {"id": entry.id}, "message": "已记录"}
