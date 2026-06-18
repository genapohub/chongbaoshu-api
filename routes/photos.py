from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from config.database import get_db
from models.pet import Pet
from models.pet_photo import PetPhoto
from models.user import User
from config.error_codes import Errors
from middleware.auth import get_current_user, TokenData
from middleware.upload import delete_local_file, validate_file, save_file

router = APIRouter(prefix="/api", tags=["photos"])

@router.post("/photos")
async def upload_photo(
    pet_id: int = Query(...),
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id).first()
    if not pet:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="宠物不存在")
    
    validate_file(file)
    
    photo_count = db.query(PetPhoto).filter(PetPhoto.pet_id == pet_id).count()
    
    sort_order = photo_count
    
    photo_path = save_file(file)
    
    photo = PetPhoto(
        pet_id=pet_id,
        photo_url=photo_path,
        sort_order=sort_order,
    )
    db.add(photo)
    
    if photo_count == 0:
        pet.avatar_photo_id = photo.id
    
    db.commit()
    db.refresh(photo)
    
    return {
        "code": 0,
        "message": "上传成功",
        "data": {
            "id": photo.id,
            "pet_id": photo.pet_id,
            "photo_url": photo.photo_url,
            "sort_order": photo.sort_order,
        }
    }

@router.delete("/photos/{photo_id}")
async def delete_photo(
    photo_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    photo = db.query(PetPhoto).filter(PetPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="照片不存在")
    
    pet = db.query(Pet).filter(Pet.id == photo.pet_id, Pet.owner_id == current_user.id).first()
    if not pet:
        raise HTTPException(status_code=Errors.PERMISSION_DENIED, detail="无权限删除此照片")
    
    delete_local_file(photo.photo_url)
    db.delete(photo)
    
    if pet.avatar_photo_id == photo.id:
        first_photo = db.query(PetPhoto).filter(PetPhoto.pet_id == pet.id).order_by(PetPhoto.sort_order).first()
        pet.avatar_photo_id = first_photo.id if first_photo else None
    
    db.commit()
    
    return {"code": 0, "message": "删除成功"}

@router.put("/photos/{photo_id}/cover")
async def set_cover_photo(
    photo_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    photo = db.query(PetPhoto).filter(PetPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=Errors.NOT_FOUND, detail="照片不存在")
    
    pet = db.query(Pet).filter(Pet.id == photo.pet_id, Pet.owner_id == current_user.id).first()
    if not pet:
        raise HTTPException(status_code=Errors.PERMISSION_DENIED, detail="无权限操作此照片")
    
    pet.avatar_photo_id = photo.id
    
    all_photos = db.query(PetPhoto).filter(PetPhoto.pet_id == pet.id).all()
    min_order = min(p.sort_order for p in all_photos)
    
    if photo.sort_order != min_order:
        current_cover = db.query(PetPhoto).filter(PetPhoto.id == pet.avatar_photo_id).first()
        if current_cover:
            current_cover.sort_order = photo.sort_order
        photo.sort_order = min_order
    
    db.commit()
    
    return {
        "code": 0,
        "message": "已设为封面",
        "data": {
            "cover_photo_id": pet.avatar_photo_id,
        }
    }
