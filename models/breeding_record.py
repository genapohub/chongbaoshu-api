from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class BreedingRecord(Base):
    __tablename__ = "breeding_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="主人ID")
    mother_id = Column(Integer, ForeignKey("pets.id"), nullable=False, comment="母犬ID")
    father_id = Column(Integer, ForeignKey("pets.id"), nullable=True, comment="父犬ID")
    father_name = Column(String(50), nullable=True, comment="父犬名称（外部）")
    father_breed = Column(String(50), nullable=True, comment="父犬品种")
    mate_name = Column(String(50), nullable=True, comment="配种对象名称")
    mate_date = Column(Date, nullable=False, comment="配种日期")
    due_date = Column(Date, nullable=True, comment="预产期")
    mating_method = Column(String(20), default="natural", comment="配种方式")
    fee = Column(Float, nullable=True, comment="配种费用")
    status = Column(String(20), default="mated", comment="状态")
    litter_count = Column(Integer, nullable=True, comment="产仔数")
    ultrasound_date = Column(Date, nullable=True, comment="孕检日期")
    delivery_date = Column(Date, nullable=True, comment="分娩日期")
    notes = Column(String, nullable=True, comment="备注")
    is_deleted = Column(Boolean, default=False, comment="软删除标记")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    mother = relationship("Pet", foreign_keys=[mother_id])
    father = relationship("Pet", foreign_keys=[father_id])
