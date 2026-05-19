

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
    role: Optional[str] = None
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
        all_photos = db.query(PetPhoto).filter(PetPhoto.pet_id == pet.id).order_by(PetPhoto.sort_order).all()
        tags = db.query(PetTag).filter(PetTag.pet_id == pet.id).all()
        
        avatar_photo = None
        if pet.avatar_photo_id:
            avatar_photo_obj = db.query(PetPhoto).filter(PetPhoto.id == pet.avatar_photo_id).first()
            if avatar_photo_obj:
                avatar_photo = avatar_photo_obj.photo_url
        
        if not avatar_photo and all_photos:
            avatar_photo = all_photos[0].photo_url
            gallery_photos = all_photos[1:] if len(all_photos) > 1 else []
        else:
            gallery_photos = [p for p in all_photos if p.id != pet.avatar_photo_id]
        
        result.append({
            "id": pet.id,
            "name": pet.name,
            "species": pet.species,
            "breed": pet.breed,
            "gender": pet.gender,
            "status": pet.status,
            "avatar_photo": avatar_photo,
            "photos": [{"id": p.id, "photo_url": p.photo_url, "sort_order": p.sort_order} for p in gallery_photos],
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
    name: str = Form(...),
    species: str = Form(...),
    breed: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    chip_no: Optional[str] = Form(None),
    chip_number: Optional[str] = Form(None),
    father_name: Optional[str] = Form(None),
    father_breed: Optional[str] = Form(None),
    mother_name: Optional[str] = Form(None),
    mother_breed: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
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
    
    chip_number = chip_number or chip_no
    
    pet = Pet(
        owner_id=current_user.id,
        name=name,
        species=species,
        breed=breed,
        gender=gender,
        birth_date=datetime.fromisoformat(birth_date) if birth_date else None,
        color=color,
        chip_no=chip_number,
        father_name=father_name,
        father_breed=father_breed,
        mother_name=mother_name,
        mother_breed=mother_breed,
        role=role,
        status="active",
    )
    db.add(pet)
    db.flush()
    
    if tags:
        tag_list = tags.split(",")
        for tag in tag_list:
            db.add(PetTag(pet_id=pet.id, tag=tag.strip()))
    
    avatar_photo = None
    if avatar:
        import os
        from uuid import uuid4
        
        upload_dir = "uploads/pets"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_ext = avatar.filename.split(".")[-1] if "." in avatar.filename else "jpg"
        file_name = f"{uuid4().hex}.{file_ext}"
        file_path = f"{upload_dir}/{file_name}"
        
        with open(file_path, "wb") as f:
            f.write(await avatar.read())
        
        photo = PetPhoto(
            pet_id=pet.id,
            photo_url=f"/{file_path}",
            sort_order=0
        )
        db.add(photo)
        db.flush()
        pet.avatar_photo_id = photo.id
        db.flush()
        avatar_photo = f"/{file_path}"
    
    db.commit()
    db.refresh(pet)
    
    return {
        "code": 0,
        "data": {"id": pet.id, "avatar_photo": avatar_photo}
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
    
    all_photos = db.query(PetPhoto).filter(PetPhoto.pet_id == pet.id).order_by(PetPhoto.sort_order).all()
    tags = db.query(PetTag).filter(PetTag.pet_id == pet.id).all()
    
    avatar_photo = None
    if pet.avatar_photo_id:
        avatar_photo_obj = db.query(PetPhoto).filter(PetPhoto.id == pet.avatar_photo_id).first()
        if avatar_photo_obj:
            avatar_photo = avatar_photo_obj.photo_url
    
    if not avatar_photo and all_photos:
        avatar_photo = all_photos[0].photo_url
        gallery_photos = all_photos[1:] if len(all_photos) > 1 else []
    else:
        gallery_photos = [p for p in all_photos if p.id != pet.avatar_photo_id]
    
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
            "avatar_photo": avatar_photo,
            "photos": [{"id": p.id, "photo_url": p.photo_url, "sort_order": p.sort_order} for p in gallery_photos],
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
