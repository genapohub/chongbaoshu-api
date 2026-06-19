from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    entry_type = Column(String(10), nullable=False, comment="类型: income/expense")
    category = Column(String(30), nullable=False, comment="分类: 配种费/疫苗药品/狗粮/寄养/销售/其他")
    amount = Column(Integer, nullable=False, comment="金额（分）")
    entry_date = Column(DateTime, nullable=False, comment="发生日期")
    description = Column(String(200), nullable=True, comment="说明")
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", backref="ledger_entries")
