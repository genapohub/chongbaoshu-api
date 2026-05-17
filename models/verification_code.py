from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from config.database import Base


class VerificationCode(Base):
    """验证码表"""
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), nullable=False, index=True, comment="手机号")
    code = Column(String(6), nullable=False, comment="验证码")
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    is_used = Column(Boolean, default=False, comment="是否已使用")
    created_at = Column(DateTime, default=func.now())
