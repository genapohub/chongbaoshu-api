from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class SubscriptionOrder(Base):
    __tablename__ = "subscription_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    tier = Column(String(20), nullable=False, comment="订阅等级")
    price = Column(DECIMAL(10, 2), nullable=False, comment="金额")
    status = Column(String(20), default="pending", comment="状态")
    transaction_no = Column(String(64), unique=True, nullable=True, comment="交易号")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User")
