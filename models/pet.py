from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class Pet(Base):
    __tablename__ = "pets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="主人ID")
    name = Column(String(50), nullable=False, comment="宠物名")
    species = Column(String(20), nullable=False, comment="物种")
    breed = Column(String(50), nullable=True, comment="品种")
    gender = Column(String(20), nullable=True, comment="性别")
    birth_date = Column(Date, nullable=True, comment="出生日期")
    color = Column(String(50), nullable=True, comment="毛色")
    chip_no = Column(String(50), nullable=True, comment="芯片号")
    status = Column(String(20), default="active", comment="状态")
    role = Column(String(20), nullable=True, comment="角色：种犬/在售/幼崽/退役")
    avatar_photo_id = Column(Integer, ForeignKey("pet_photos.id"), nullable=True, comment="封面照片ID")
    father_id = Column(Integer, nullable=True, comment="父亲ID")
    mother_id = Column(Integer, nullable=True, comment="母亲ID")
    father_name = Column(String(50), nullable=True, comment="父亲名（外部）")
    father_breed = Column(String(50), nullable=True, comment="父亲品种")
    grandfather_p_name = Column(String(50), nullable=True, comment="祖父名（父系）")
    grandmother_p_name = Column(String(50), nullable=True, comment="祖母名（父系）")
    mother_name = Column(String(50), nullable=True, comment="母亲名（外部）")
    mother_breed = Column(String(50), nullable=True, comment="母亲品种")
    grandfather_m_name = Column(String(50), nullable=True, comment="外祖父名（母系）")
    grandmother_m_name = Column(String(50), nullable=True, comment="外祖母名（母系）")
    breeding_record_id = Column(Integer, ForeignKey("breeding_records.id"), nullable=True, comment="来源繁育记录ID")
    is_neutered = Column(Boolean, default=False, comment="是否绝育")
    is_deleted = Column(Boolean, default=False, comment="软删除标记")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    photos = relationship("PetPhoto", foreign_keys="PetPhoto.pet_id", back_populates="pet")
    tags = relationship("PetTag", back_populates="pet")
    avatar_photo = relationship("PetPhoto", foreign_keys=[avatar_photo_id])
