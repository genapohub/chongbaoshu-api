from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from config.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, nullable=False, comment="微信openid")
    unionid = Column(String(64), unique=True, nullable=True, comment="微信unionid")
    nickname = Column(String(50), nullable=True, comment="昵称")
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    phone = Column(String(20), nullable=True, comment="手机号")
    kennel_name = Column(String(100), nullable=True, comment="宠舍名称")
    kennel_address = Column(String(200), nullable=True, comment="宠舍地址")
    kennel_intro = Column(String, nullable=True, comment="宠舍简介")
    subscription_tier = Column(String(20), default="free", comment="订阅等级（SSOT，Subscription 表为审计镜像）")
    subscription_expire = Column(DateTime, nullable=True, comment="订阅过期时间")
    remind_vaccine = Column(Boolean, default=True, comment="疫苗提醒开关")
    remind_deworm = Column(Boolean, default=True, comment="驱虫提醒开关")
    remind_due = Column(Boolean, default=True, comment="预产期提醒开关")
    kennel_logo = Column(String(500), nullable=True, comment="宠舍Logo")
    main_breeds = Column(String(500), nullable=True, comment="主营品种")
    wechat = Column(String(50), nullable=True, comment="微信号")
    remind_vaccine_days = Column(Integer, default=7, comment="疫苗提前天数")
    remind_deworm_days = Column(Integer, default=7, comment="驱虫提前天数")
    remind_due_days = Column(Integer, default=7, comment="预产期提前天数")
    notify_in_app = Column(Boolean, default=True, comment="站内通知开关")
    notify_wechat = Column(Boolean, default=False, comment="微信推送开关")
    notify_sms = Column(Boolean, default=False, comment="短信通知开关")
    invite_code = Column(String(20), unique=True, nullable=True, comment="邀请码")
    subscription_source = Column(String(20), default=None, nullable=True, comment="订阅来源: paid/reward/none")
    is_active = Column(Boolean, default=True, comment="是否活跃")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
