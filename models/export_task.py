from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class ExportTask(Base):
    __tablename__ = "export_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    type = Column(String(20), nullable=False, comment="导出类型")
    status = Column(String(20), default="pending", comment="状态")
    file_path = Column(String(500), nullable=True, comment="文件路径")
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User")
