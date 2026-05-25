from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class InviteRecord(Base):
    __tablename__ = "invite_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="邀请人ID")
    invitee_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="被邀请人ID")
    invite_code = Column(String(20), nullable=False, comment="邀请码")
    status = Column(String(20), default="pending", comment="状态: pending/redeemed/rewarded")
    reward_days = Column(Integer, default=7, comment="奖励天数")
    redeemed_at = Column(DateTime, nullable=True, comment="领取时间")
    created_at = Column(DateTime, default=func.now())

    inviter = relationship("User", foreign_keys=[inviter_id])
    invitee = relationship("User", foreign_keys=[invitee_id])
