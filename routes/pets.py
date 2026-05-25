

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Body
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sa_func
from datetime import datetime

from config.database import get_db
from models.user import User
from models.pet import Pet
from models.pet_photo import PetPhoto
from models.pet_tag import PetTag
from middleware.auth import get_current_user, TokenData
from utils.helpers import get_user_limits, get_effective_tier
from utils.sanitize import sanitize_string

router = APIRouter(prefix="/api/pets", tags=["pets"])

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
    grandfather_p_name: Optional[str] = None
    grandmother_p_name: Optional[str] = None
    mother_name: Optional[str] = None
    mother_breed: Optional[str] = None
    grandfather_m_name: Optional[str] = None
    grandmother_m_name: Optional[str] = None
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
    
    # 批量预加载 photos 和 tags，避免 N+1 查询
    pet_ids = [pet.id for pet in pets]
    
    if pet_ids:
        all_photos = db.query(PetPhoto).filter(PetPhoto.pet_id.in_(pet_ids)).order_by(PetPhoto.pet_id, PetPhoto.sort_order).all()
        all_tags = db.query(PetTag).filter(PetTag.pet_id.in_(pet_ids)).all()
    else:
        all_photos = []
        all_tags = []
    
    # 按 pet_id 分组
    photos_by_pet = {}
    for p in all_photos:
        photos_by_pet.setdefault(p.pet_id, []).append(p)
    
    tags_by_pet = {}
    for t in all_tags:
        tags_by_pet.setdefault(t.pet_id, []).append(t)
    
    # avatar_photo_id -> photo_url 的映射（从已加载的 photos 中查找）
    avatar_ids = {pet.avatar_photo_id for pet in pets if pet.avatar_photo_id}
    avatar_photos_map = {}
    if avatar_ids:
        for p in all_photos:
            if p.id in avatar_ids:
                avatar_photos_map[p.id] = p.photo_url
    
    result = []
    for pet in pets:
        pet_photos = photos_by_pet.get(pet.id, [])
        tags = tags_by_pet.get(pet.id, [])
        
        avatar_photo = avatar_photos_map.get(pet.avatar_photo_id) if pet.avatar_photo_id else None
        
        if not avatar_photo and pet_photos:
            avatar_photo = pet_photos[0].photo_url
            gallery_photos = pet_photos[1:] if len(pet_photos) > 1 else []
        else:
            gallery_photos = [p for p in pet_photos if p.id != pet.avatar_photo_id]
        
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
            "platform_cert_no": pet.platform_cert_no,
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
    grandfather_p_name: Optional[str] = Form(None),
    grandmother_p_name: Optional[str] = Form(None),
    mother_name: Optional[str] = Form(None),
    mother_breed: Optional[str] = Form(None),
    grandfather_m_name: Optional[str] = Form(None),
    grandmother_m_name: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")
    
    limits = get_user_limits(get_effective_tier(user))
    
    current_pets = db.query(Pet).filter(
        Pet.owner_id == current_user.id,
        Pet.is_deleted == False
    ).count()
    
    if limits["maxPets"] != "unlimited" and current_pets >= limits["maxPets"]:
        raise HTTPException(status_code=2001, detail="已达宠物数量上限，请升级订阅")
    
    chip_number = chip_number or chip_no
    
    pet = Pet(
        owner_id=current_user.id,
        name=sanitize_string(name),
        species=species,
        breed=sanitize_string(breed) if breed else None,
        gender=gender,
        birth_date=datetime.fromisoformat(birth_date) if birth_date else None,
        color=sanitize_string(color) if color else None,
        chip_no=sanitize_string(chip_number) if chip_number else None,
        father_name=sanitize_string(father_name) if father_name else None,
        father_breed=sanitize_string(father_breed) if father_breed else None,
        grandfather_p_name=sanitize_string(grandfather_p_name) if grandfather_p_name else None,
        grandmother_p_name=sanitize_string(grandmother_p_name) if grandmother_p_name else None,
        mother_name=sanitize_string(mother_name) if mother_name else None,
        mother_breed=sanitize_string(mother_breed) if mother_breed else None,
        grandfather_m_name=sanitize_string(grandfather_m_name) if grandfather_m_name else None,
        grandmother_m_name=sanitize_string(grandmother_m_name) if grandmother_m_name else None,
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
        from middleware.upload import validate_file, MAX_FILE_SIZE
        
        validate_file(avatar)
        
        content = await avatar.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=1001, detail="头像文件大小超过限制（最大5MB）")
        
        import os
        from uuid import uuid4
        from pathlib import Path
        
        upload_dir = "uploads/pets"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_ext = Path(avatar.filename).suffix.lower() if avatar.filename else ".jpg"
        file_name = f"{uuid4().hex}{file_ext}"
        file_path = f"{upload_dir}/{file_name}"
        
        with open(file_path, "wb") as f:
            f.write(content)
        
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
            "platform_cert_no": pet.platform_cert_no,
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
    grandfather_p_name: Optional[str] = None
    grandmother_p_name: Optional[str] = None
    mother_name: Optional[str] = None
    mother_breed: Optional[str] = None
    grandfather_m_name: Optional[str] = None
    grandmother_m_name: Optional[str] = None
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
        pet.name = sanitize_string(request.name)
    if request.species is not None:
        pet.species = request.species
    if request.breed is not None:
        pet.breed = sanitize_string(request.breed)
    if request.gender is not None:
        pet.gender = request.gender
    if request.birth_date is not None:
        pet.birth_date = datetime.fromisoformat(request.birth_date) if request.birth_date else None
    if request.color is not None:
        pet.color = sanitize_string(request.color)
    if request.chip_no is not None:
        pet.chip_no = sanitize_string(request.chip_no)
    if request.father_name is not None:
        pet.father_name = sanitize_string(request.father_name)
    if request.father_breed is not None:
        pet.father_breed = sanitize_string(request.father_breed)
    if request.grandfather_p_name is not None:
        pet.grandfather_p_name = sanitize_string(request.grandfather_p_name)
    if request.grandmother_p_name is not None:
        pet.grandmother_p_name = sanitize_string(request.grandmother_p_name)
    if request.mother_name is not None:
        pet.mother_name = sanitize_string(request.mother_name)
    if request.mother_breed is not None:
        pet.mother_breed = sanitize_string(request.mother_breed)
    if request.grandfather_m_name is not None:
        pet.grandfather_m_name = sanitize_string(request.grandfather_m_name)
    if request.grandmother_m_name is not None:
        pet.grandmother_m_name = sanitize_string(request.grandmother_m_name)
    
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

@router.post("/{pet_id}/assign-cert-no")
async def assign_cert_no(
    pet_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """为宠物分配平台认证编号，格式：CBS-P-{year}-{seq:05d}"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=1002, detail="用户不存在")

    if get_effective_tier(user) != "pro":
        raise HTTPException(status_code=2001, detail="仅 Pro 用户可分配平台认证编号")

    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id, Pet.is_deleted == False).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    # 幂等：若已有认证编号，直接返回
    if pet.platform_cert_no:
        return {
            "code": 0,
            "data": {"platform_cert_no": pet.platform_cert_no}
        }

    # 生成年份前缀
    year = datetime.now().year
    prefix = f"CBS-P-{year}-"

    # 查询当年已分配的最大序号
    max_cert_no = db.query(sa_func.max(Pet.platform_cert_no)).filter(
        Pet.platform_cert_no.like(f"{prefix}%")
    ).scalar()

    if max_cert_no:
        # 解析序号部分
        try:
            last_seq = int(max_cert_no.split("-")[-1])
        except (ValueError, IndexError):
            last_seq = 0
        next_seq = last_seq + 1
    else:
        next_seq = 1

    new_cert_no = f"{prefix}{next_seq:05d}"

    pet.platform_cert_no = new_cert_no
    db.commit()
    db.refresh(pet)

    return {
        "code": 0,
        "data": {"platform_cert_no": pet.platform_cert_no}
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
    
    # 获取父母信息
    father = None
    mother = None
    grandfather_p = None
    grandmother_p = None
    grandfather_m = None
    grandmother_m = None
    
    if pet.father_id:
        father = db.query(Pet).filter(Pet.id == pet.father_id, Pet.is_deleted == False).first()
        if father and generation > 1:
            grandfather_p = db.query(Pet).filter(Pet.id == father.father_id, Pet.is_deleted == False).first()
            grandmother_p = db.query(Pet).filter(Pet.id == father.mother_id, Pet.is_deleted == False).first()
    
    if pet.mother_id:
        mother = db.query(Pet).filter(Pet.id == pet.mother_id, Pet.is_deleted == False).first()
        if mother and generation > 1:
            grandfather_m = db.query(Pet).filter(Pet.id == mother.father_id, Pet.is_deleted == False).first()
            grandmother_m = db.query(Pet).filter(Pet.id == mother.mother_id, Pet.is_deleted == False).first()
    
    # 构建返回数据
    pedigree_data = {
        "pet_id": pet.id,
        "pet_name": pet.name,
        "breed": pet.breed,
        "color": pet.color,
        "chip_number": pet.chip_no,
        "birth_date": pet.birth_date.isoformat() if pet.birth_date else None,
        "registration_number": pet.chip_no,
        "platform_cert_no": pet.platform_cert_no,
        # 父亲
        "father_id": pet.father_id,
        "father_name": pet.father_name or (father.name if father else None),
        "father_breed": pet.father_breed or (father.breed if father else None),
        # 母亲
        "mother_id": pet.mother_id,
        "mother_name": pet.mother_name or (mother.name if mother else None),
        "mother_breed": pet.mother_breed or (mother.breed if mother else None),
        # 父方祖父
        "father_father_id": grandfather_p.id if grandfather_p else None,
        "father_father_name": pet.grandfather_p_name or (grandfather_p.name if grandfather_p else None),
        "father_father_breed": grandfather_p.breed if grandfather_p else None,
        # 父方祖母
        "father_mother_id": grandmother_p.id if grandmother_p else None,
        "father_mother_name": pet.grandmother_p_name or (grandmother_p.name if grandmother_p else None),
        "father_mother_breed": grandmother_p.breed if grandmother_p else None,
        # 父方祖父的父亲
        "father_father_father_id": None,
        "father_father_father_name": None,
        # 父方祖父的母亲
        "father_father_mother_id": None,
        "father_father_mother_name": None,
        # 父方祖母的父亲
        "father_mother_father_id": None,
        "father_mother_father_name": None,
        # 父方祖母的母亲
        "father_mother_mother_id": None,
        "father_mother_mother_name": None,
        # 母方祖父
        "mother_father_id": grandfather_m.id if grandfather_m else None,
        "mother_father_name": pet.grandfather_m_name or (grandfather_m.name if grandfather_m else None),
        "mother_father_breed": grandfather_m.breed if grandfather_m else None,
        # 母方祖母
        "mother_mother_id": grandmother_m.id if grandmother_m else None,
        "mother_mother_name": pet.grandmother_m_name or (grandmother_m.name if grandmother_m else None),
        "mother_mother_breed": grandmother_m.breed if grandmother_m else None,
        # 母方祖父的父亲
        "mother_father_father_id": None,
        "mother_father_father_name": None,
        # 母方祖父的母亲
        "mother_father_mother_id": None,
        "mother_father_mother_name": None,
        # 母方祖母的父亲
        "mother_mother_father_id": None,
        "mother_mother_father_name": None,
        # 母方祖母的母亲
        "mother_mother_mother_id": None,
        "mother_mother_mother_name": None,
        # 额外信息
        "kennel_name": user.kennel_name,
        "generation": generation,
        "is_pro": get_effective_tier(user) == "pro",
    }
    
    # 非Pro用户隐藏详细信息
    if get_effective_tier(user) != "pro":
        return {
            "code": 0,
            "data": {
                "pet_id": pet.id,
                "pet_name": pet.name,
                "registration_name": None,
                "registration_number": pet.chip_no,
                "platform_cert_no": pet.platform_cert_no,
                "kennel_name": user.kennel_name,
                "color": pet.color,
                "chip_number": pet.chip_no,
                "birth_date": pet.birth_date.isoformat() if pet.birth_date else None,
                "father_name": None,
                "mother_name": None,
                "father_father_name": None,
                "father_mother_name": None,
                "mother_father_name": None,
                "mother_mother_name": None,
                "father_father_father_name": None,
                "father_father_mother_name": None,
                "father_mother_father_name": None,
                "father_mother_mother_name": None,
                "mother_father_father_name": None,
                "mother_father_mother_name": None,
                "mother_mother_father_name": None,
                "mother_mother_mother_name": None,
                "is_pro": False,
                "message": "升级为Pro用户可查看完整血统树"
            }
        }
    
    return {
        "code": 0,
        "data": pedigree_data
    }
