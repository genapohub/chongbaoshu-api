from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class HealthRecord(Base):
    __tablename__ = "health_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True, comment="宠物ID")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="主人ID")
    type = Column(String(20), nullable=False, comment="记录类型")
    vaccine_type = Column(String(50), nullable=True, comment="疫苗类型")
    record_date = Column(Date, nullable=False, comment="记录日期")
    next_date = Column(Date, nullable=True, comment="下次日期")
    deworm_type = Column(String(20), nullable=True, comment="驱虫类型")
    medicine_name = Column(String(100), nullable=True, comment="药品名称")
    dosage = Column(String(50), nullable=True, comment="剂量")
    batch_no = Column(String(50), nullable=True, comment="批号")
    vet_hospital = Column(String(100), nullable=True, comment="兽医/医院")
    vaccine_round = Column(Integer, nullable=True, comment="针次")
    deworm_interval = Column(Integer, nullable=True, comment="驱虫间隔天数")
    notes = Column(String, nullable=True, comment="备注")
    is_deleted = Column(Boolean, default=False, comment="软删除标记")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    pet = relationship("Pet")
    owner = relationship("User")
