from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class PetPhoto(Base):
    __tablename__ = "pet_photos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True, comment="宠物ID")
    photo_url = Column(String(500), nullable=False, comment="照片URL")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=func.now())

    pet = relationship("Pet", foreign_keys=[pet_id])
