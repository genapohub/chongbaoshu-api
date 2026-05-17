

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Body
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from config.database import SessionLocal
from models.user import User
from models.pet import Pet
from models.pet_photo import PetPhoto
from models.pet_tag import PetTag
from middleware.auth import get_current_user, TokenData
from utils.helpers import get_user_limits

router = APIRouter(prefix="/api/pets", tags=["pets"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CreatePetRequest(BaseModel):
    name: str
    species: str
    breed: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    color: Optional[str] = None
    chip_no: Optional[str] = None
    chip_number: Optional[str] = None
    father_name: Optional[str] = None
    father_breed: Optional[str] = None
    mother_name: Optional[str] = None
    mother_breed: Optional[str] = None
    tags: Optional[List[str]] = None

@router.get("")
async def get_pets(
    species: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Pet).filter(Pet.owner_id == current_user.id, Pet.is_deleted == False)
    
    if species:
        query = query.filter(Pet.species == species)
    if status:
        query = query.filter(Pet.status == status)
    
    total = query.count()
    pets = query.offset((page - 1) * pageSize).limit(pageSize).all()
    
    result = []
    for pet in pets:
        photos = db.query(PetPhoto).filter(PetPhoto.pet_id == pet.id, PetPhoto.sort_order == 0).first()
        tags = db.query(PetTag).filter(PetTag.pet_id == pet.id).all()
        result.append({
            "id": pet.id,
            "name": pet.name,
            "species": pet.species,
            "breed": pet.breed,
            "gender": pet.gender,
            "status": pet.status,
            "avatar_photo": photos.photo_url if photos else None,
            "tags": [t.tag for t in tags],
            "birth_date": pet.birth_date,
            "updated_at": pet.updated_at,
        })
    
    return {
        "code": 0,
        "data": {
            "list": result,
            "total": total,
            "page": page,
            "pageSize": pageSize,
        }
    }

@router.post("")
async def create_pet(
    request: CreatePetRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    limits = get_user_limits(user.subscription_tier)
    
    current_pets = db.query(Pet).filter(
        Pet.owner_id == current_user.id,
        Pet.is_deleted == False
    ).count()
    
    if limits["maxPets"] != "unlimited" and current_pets >= limits["maxPets"]:
        raise HTTPException(status_code=2001, detail="已达宠物数量上限，请升级订阅")
    
    chip_number = request.chip_number or request.chip_no
    
    pet = Pet(
        owner_id=current_user.id,
        name=request.name,
        species=request.species,
        breed=request.breed,
        gender=request.gender,
        birth_date=datetime.fromisoformat(request.birth_date) if request.birth_date else None,
        color=request.color,
        chip_no=chip_number,
        father_name=request.father_name,
        father_breed=request.father_breed,
        mother_name=request.mother_name,
        mother_breed=request.mother_breed,
        status="active",
    )
    db.add(pet)
    db.flush()
    
    if request.tags:
        for i, tag in enumerate(request.tags):
            db.add(PetTag(pet_id=pet.id, tag=tag))
    
    db.commit()
    db.refresh(pet)
    
    return {
        "code": 0,
        "data": {"id": pet.id}
    }

@router.get("/{pet_id}")
async def get_pet(
    pet_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    
    photos = db.query(PetPhoto).filter(PetPhoto.pet_id == pet.id).order_by(PetPhoto.sort_order).all()
    tags = db.query(PetTag).filter(PetTag.pet_id == pet.id).all()
    
    return {
        "code": 0,
        "data": {
            "id": pet.id,
            "name": pet.name,
            "species": pet.species,
            "breed": pet.breed,
            "gender": pet.gender,
            "birth_date": pet.birth_date,
            "color": pet.color,
            "chip_number": pet.chip_no,
            "status": pet.status,
            "is_neutered": pet.is_neutered,
            "father_name": pet.father_name,
            "father_breed": pet.father_breed,
            "mother_name": pet.mother_name,
            "mother_breed": pet.mother_breed,
            "photos": [{"id": p.id, "photo_url": p.photo_url, "sort_order": p.sort_order} for p in photos],
            "tags": [t.tag for t in tags],
            "created_at": pet.created_at,
            "updated_at": pet.updated_at,
        }
    }

class UpdatePetRequest(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    breed: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    color: Optional[str] = None
    chip_no: Optional[str] = None
    father_name: Optional[str] = None
    father_breed: Optional[str] = None
    mother_name: Optional[str] = None
    mother_breed: Optional[str] = None
    tags: Optional[List[str]] = None

@router.put("/{pet_id}")
async def update_pet(
    pet_id: int,
    request: UpdatePetRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    
    if request.name is not None:
        pet.name = request.name
    if request.species is not None:
        pet.species = request.species
    if request.breed is not None:
        pet.breed = request.breed
    if request.gender is not None:
        pet.gender = request.gender
    if request.birth_date is not None:
        pet.birth_date = datetime.fromisoformat(request.birth_date) if request.birth_date else None
    if request.color is not None:
        pet.color = request.color
    if request.chip_no is not None:
        pet.chip_no = request.chip_no
    if request.father_name is not None:
        pet.father_name = request.father_name
    if request.father_breed is not None:
        pet.father_breed = request.father_breed
    if request.mother_name is not None:
        pet.mother_name = request.mother_name
    if request.mother_breed is not None:
        pet.mother_breed = request.mother_breed
    
    if request.tags is not None:
        db.query(PetTag).filter(PetTag.pet_id == pet.id).delete()
        for tag in request.tags:
            db.add(PetTag(pet_id=pet.id, tag=tag))
    
    db.commit()
    
    return {
        "code": 0,
        "data": {"id": pet.id}
    }

@router.delete("/{pet_id}")
async def delete_pet(
    pet_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    
    pet.is_deleted = True
    db.commit()
    
    return {
        "code": 0,
        "data": {}
    }

@router.get("/{pet_id}/pedigree")
async def get_pedigree(
    pet_id: int,
    generation: int = Query(default=3, ge=1, le=5),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    
    if user.subscription_tier != "pro":
        return {
            "code": 0,
            "data": {
                "pet_id": pet.id,
                "pet_name": pet.name,
                "generation": generation,
                "pedigree_tree": None,
                "is_pro": False,
                "message": "升级为Pro用户可查看完整血统树"
            }
        }
    
    return {
        "code": 0,
        "data": {
            "pet_id": pet.id,
            "pet_name": pet.name,
            "generation": generation,
            "pedigree_tree": None,
            "is_pro": True,
        }
    }
