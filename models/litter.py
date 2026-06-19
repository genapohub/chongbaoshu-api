from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class Litter(Base):
    __tablename__ = "litters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="繁育者ID")
    breeding_record_id = Column(Integer, ForeignKey("breeding_records.id"), nullable=True, comment="来源繁育记录ID")
    mother_id = Column(Integer, ForeignKey("pets.id"), nullable=False, comment="母犬/猫ID")
    father_id = Column(Integer, ForeignKey("pets.id"), nullable=True, comment="父犬/猫ID")
    birth_date = Column(Date, nullable=False, comment="出生日期")
    litter_size = Column(Integer, default=0, comment="产仔数量")
    notes = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", backref="litters")
    breeding_record = relationship("BreedingRecord", backref="litter")
    mother = relationship("Pet", foreign_keys=[mother_id], backref="litters_as_mother")
    father = relationship("Pet", foreign_keys=[father_id], backref="litters_as_father")
