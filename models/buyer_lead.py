from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class BuyerLead(Base):
    __tablename__ = "buyer_leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="繁育者ID")
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=True, comment="感兴趣的宠物ID")
    buyer_name = Column(String(50), nullable=False, comment="买家昵称/姓名")
    buyer_wechat = Column(String(50), nullable=True, comment="买家微信号")
    buyer_phone = Column(String(20), nullable=True, comment="买家手机号")
    status = Column(String(20), default="consulting", comment="状态: consulting/visited/negotiating/sold/lost")
    budget = Column(String(50), nullable=True, comment="买家预算/报价")
    notes = Column(Text, nullable=True, comment="备注（如：家里有小孩，要温顺的）")
    last_followed_at = Column(DateTime, nullable=True, comment="最后跟进时间")
    is_deleted = Column(Boolean, default=False, comment="软删除")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", backref="buyer_leads")
    pet = relationship("Pet", backref="buyer_lead_refs")
