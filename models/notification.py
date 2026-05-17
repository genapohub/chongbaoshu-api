from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    type = Column(String(20), nullable=False, comment="通知类型")
    title = Column(String(100), nullable=False, comment="标题")
    content = Column(String(500), nullable=True, comment="内容")
    data = Column(JSON, nullable=True, comment="附加数据")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime, default=func.now())

    user = relationship("User")
