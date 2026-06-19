from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class PetSale(Base):
    __tablename__ = "pet_sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="繁育者ID")
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, comment="售出的宠物ID")
    buyer_lead_id = Column(Integer, ForeignKey("buyer_leads.id"), nullable=True, comment="关联意向客户ID")
    buyer_name = Column(String(50), nullable=False, comment="买家名（冗余，方便快速查询）")
    sale_price = Column(Integer, nullable=False, comment="售价（分）")
    sale_date = Column(DateTime, nullable=False, comment="成交日期")
    items_included = Column(String(200), nullable=True, comment="附带物品（如：3斤狗粮+疫苗本）")
    notes = Column(Text, nullable=True, comment="备注")
    is_deleted = Column(Boolean, default=False, comment="软删除")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", backref="pet_sales")
    pet = relationship("Pet", backref="sale_record")
    buyer_lead = relationship("BuyerLead", backref="sale")
