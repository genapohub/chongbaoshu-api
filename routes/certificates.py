from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, date
from config.database import get_db
from models.pet import Pet
from models.pedigree_certificate import PedigreeCertificate
from models.user import User
from config.error_codes import Errors
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
        PedigreeCertificate.cert_no.like(f"CBS-{year}-%")
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
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="宠物不存在")
    
    certificates = db.query(PedigreeCertificate).filter(
        PedigreeCertificate.pet_id == pet_id,
        PedigreeCertificate.owner_id == current_user.id
    ).order_by(PedigreeCertificate.created_at.desc()).all()
    
    result = []
    for cert in certificates:
        result.append({
            "id": cert.id,
            "pet_id": cert.pet_id,
            "certificate_no": cert.cert_no,
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
        raise HTTPException(status_code=Errors.PERMISSION_DENIED, detail="血统证书仅Pro用户可用")
    
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="宠物不存在")
    
    cert_no = generate_cert_no(db)
    pedigree_tree = build_pedigree_tree(db, pet, request.generation or 3)
    
    certificate = PedigreeCertificate(
        pet_id=pet_id,
        owner_id=current_user.id,
        cert_no=cert_no,
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
            "certificate_no": certificate.cert_no,
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
        raise HTTPException(status_code=Errors.PERMISSION_DENIED, detail="血统证书仅Pro用户可用")
    
    certificate = db.query(PedigreeCertificate).filter(
        PedigreeCertificate.id == cert_id,
        PedigreeCertificate.owner_id == current_user.id
    ).first()
    
    if not certificate:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="证书不存在")
    
    if certificate.status != "draft":
        raise HTTPException(status_code=Errors.BUSINESS_ERROR, detail="只有草稿状态的证书可以签发")
    
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
        raise HTTPException(status_code=Errors.PERMISSION_DENIED, detail="血统证书仅Pro用户可用")
    
    certificate = db.query(PedigreeCertificate).filter(
        PedigreeCertificate.id == cert_id,
        PedigreeCertificate.owner_id == current_user.id
    ).first()
    
    if not certificate:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="证书不存在")
    
    if certificate.status != "issued":
        raise HTTPException(status_code=Errors.BUSINESS_ERROR, detail="只有已签发的证书可以撤销")
    
    if not request.reason:
        raise HTTPException(status_code=Errors.PARAM_INVALID, detail="撤销原因不能为空")
    
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

# ── 公开接口：买家扫码验证血统证书（无需登录） ──

class CertVerifyResponse(BaseModel):
    cert_no: str
    pet_name: str
    pet_species: str
    pet_breed: Optional[str] = None
    pet_gender: Optional[str] = None
    pet_birth_date: Optional[str] = None
    father_name: Optional[str] = None
    father_breed: Optional[str] = None
    mother_name: Optional[str] = None
    mother_breed: Optional[str] = None
    kennel_name: str = ""
    issue_date: Optional[str] = None
    status: str = ""

@router.get("/certificates/public/{cert_no}", dependencies=[])
async def verify_certificate_public(
    cert_no: str,
    db: Session = Depends(get_db)
):
    """公开接口：通过证书编号查询血统证书（买家扫码验证），无需登录"""
    certificate = db.query(PedigreeCertificate).filter(
        PedigreeCertificate.cert_no == cert_no,
        PedigreeCertificate.status == "active"
    ).first()

    if not certificate:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="证书不存在或已撤销")

    pet = db.query(Pet).filter(Pet.id == certificate.pet_id).first()
    owner = db.query(User).filter(User.id == certificate.owner_id).first()

    # 增加分享计数
    certificate.share_count = (certificate.share_count or 0) + 1
    db.commit()

    return {
        "code": 0,
        "data": {
            "cert_no": certificate.cert_no,
            "pet_name": pet.name if pet else "",
            "pet_species": pet.species if pet else "",
            "pet_breed": pet.breed if pet else None,
            "pet_gender": pet.gender if pet else None,
            "pet_birth_date": pet.birth_date.strftime("%Y-%m-%d") if pet and pet.birth_date else None,
            "father_name": certificate.pedigree_tree.get("father_name") if certificate.pedigree_tree else None,
            "father_breed": certificate.pedigree_tree.get("father_breed") if certificate.pedigree_tree else None,
            "mother_name": certificate.pedigree_tree.get("mother_name") if certificate.pedigree_tree else None,
            "mother_breed": certificate.pedigree_tree.get("mother_breed") if certificate.pedigree_tree else None,
            "kennel_name": owner.kennel_name if owner else "",
            "issue_date": certificate.issue_date.strftime("%Y-%m-%d") if certificate.issue_date else None,
            "status": certificate.status,
        }
    }
