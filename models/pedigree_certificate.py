from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class PedigreeCertificate(Base):
    __tablename__ = "pedigree_certificates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, comment="宠物ID")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="主人ID")
    cert_no = Column(String(50), unique=True, nullable=False, comment="证书编号")
    issuer = Column(String(100), nullable=True, comment="颁发机构")
    issue_date = Column(DateTime, nullable=True, comment="颁发日期")
    status = Column(String(20), default="active", comment="状态")
    generation = Column(Integer, default=3, comment="血统代数")
    pedigree_tree = Column(JSON, nullable=True, comment="血统树数据")
    share_count = Column(Integer, default=0, comment="分享次数")
    revoke_reason = Column(String(500), nullable=True, comment="撤销原因")
    revoked_at = Column(DateTime, nullable=True, comment="撤销时间")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    pet = relationship("Pet")
    owner = relationship("User")
