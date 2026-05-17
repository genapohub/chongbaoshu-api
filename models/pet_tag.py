from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class PetTag(Base):
    __tablename__ = "pet_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, comment="宠物ID")
    tag = Column(String(30), nullable=False, comment="标签内容")
    created_at = Column(DateTime, default=func.now())

    pet = relationship("Pet", back_populates="tags")
