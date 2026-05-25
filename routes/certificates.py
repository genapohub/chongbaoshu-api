from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, date
from config.database import get_db
from models.pet import Pet
from models.pedigree_certificate import PedigreeCertificate
from models.user import User
from middleware.auth import get_current_user, TokenData
from utils.helpers import get_effective_tier

router = APIRouter(prefix="/api", tags=["certificates"])

class CreateCertificateRequest(BaseModel):
    pet_id: int
    generation: Optional[int] = 3

class IssueCertificateRequest(BaseModel):
    pass

class RevokeCertificateRequest(BaseModel):
    reason: str

def generate_cert_no(db: Session) -> str:
    year = datetime.utcnow().year
    count = db.query(PedigreeCertificate).filter(
        PedigreeCertificate.certificate_no.like(f"CBS-{year}-%")
    ).count()
    return f"CBS-{year}-{str(count + 1).zfill(5)}"

def build_pedigree_tree(db: Session, pet: Pet, generation: int = 3) -> dict:
    if generation == 0 or not pet:
        return None
    
    tree = {
        "id": pet.id,
        "name": pet.name,
        "breed": pet.breed,
        "gender": pet.gender,
    }
    
    if generation > 1:
        if pet.father_id:
            father = db.query(Pet).filter(Pet.id == pet.father_id).first()
            tree["father"] = build_pedigree_tree(db, father, generation - 1)
        if pet.mother_id:
            mother = db.query(Pet).filter(Pet.id == pet.mother_id).first()
            tree["mother"] = build_pedigree_tree(db, mother, generation - 1)
    
    return tree

@router.get("/pets/{pet_id}/certificates")
async def get_pet_certificates(
    pet_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    
    certificates = db.query(PedigreeCertificate).filter(
        PedigreeCertificate.pet_id == pet_id,
        PedigreeCertificate.owner_id == current_user.id
    ).order_by(PedigreeCertificate.created_at.desc()).all()
    
    result = []
    for cert in certificates:
        result.append({
            "id": cert.id,
            "pet_id": cert.pet_id,
            "certificate_no": cert.certificate_no,
            "status": cert.status,
            "generation": cert.generation,
            "issue_date": cert.issue_date,
            "share_count": cert.share_count,
            "created_at": cert.created_at,
        })
    
    return {
        "code": 0,
        "data": result
    }

@router.post("/pets/{pet_id}/certificates")
async def create_certificate(
    pet_id: int,
    request: CreateCertificateRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if get_effective_tier(user) != "pro":
        raise HTTPException(status_code=403, detail="血统证书仅Pro用户可用")
    
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    
    cert_no = generate_cert_no(db)
    pedigree_tree = build_pedigree_tree(db, pet, request.generation or 3)
    
    certificate = PedigreeCertificate(
        pet_id=pet_id,
        owner_id=current_user.id,
        certificate_no=cert_no,
        generation=request.generation or 3,
        pedigree_tree=pedigree_tree,
        status="draft",
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    
    return {
        "code": 0,
        "message": "证书创建成功",
        "data": {
            "id": certificate.id,
            "certificate_no": certificate.certificate_no,
            "status": certificate.status,
            "generation": certificate.generation,
            "pedigree_tree": pedigree_tree,
        }
    }

@router.put("/certificates/{cert_id}/issue")
async def issue_certificate(
    cert_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if get_effective_tier(user) != "pro":
        raise HTTPException(status_code=403, detail="血统证书仅Pro用户可用")
    
    certificate = db.query(PedigreeCertificate).filter(
        PedigreeCertificate.id == cert_id,
        PedigreeCertificate.owner_id == current_user.id
    ).first()
    
    if not certificate:
        raise HTTPException(status_code=404, detail="证书不存在")
    
    if certificate.status != "draft":
        raise HTTPException(status_code=5005, detail="只有草稿状态的证书可以签发")
    
    certificate.status = "issued"
    certificate.issue_date = datetime.utcnow().date()
    db.commit()
    
    return {
        "code": 0,
        "message": "证书签发成功",
        "data": {
            "id": certificate.id,
            "status": certificate.status,
            "issue_date": certificate.issue_date,
        }
    }

@router.put("/certificates/{cert_id}/revoke")
async def revoke_certificate(
    cert_id: int,
    request: RevokeCertificateRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if get_effective_tier(user) != "pro":
        raise HTTPException(status_code=403, detail="血统证书仅Pro用户可用")
    
    certificate = db.query(PedigreeCertificate).filter(
        PedigreeCertificate.id == cert_id,
        PedigreeCertificate.owner_id == current_user.id
    ).first()
    
    if not certificate:
        raise HTTPException(status_code=404, detail="证书不存在")
    
    if certificate.status != "issued":
        raise HTTPException(status_code=5005, detail="只有已签发的证书可以撤销")
    
    if not request.reason:
        raise HTTPException(status_code=1001, detail="撤销原因不能为空")
    
    certificate.status = "revoked"
    certificate.revoke_reason = request.reason
    certificate.revoked_at = datetime.utcnow()
    db.commit()
    
    return {
        "code": 0,
        "message": "证书已撤销",
        "data": {
            "id": certificate.id,
            "status": certificate.status,
            "revoke_reason": certificate.revoke_reason,
            "revoked_at": certificate.revoked_at,
        }
    }
