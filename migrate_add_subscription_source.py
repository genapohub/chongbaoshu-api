"""
[已废弃] 此脚本已被 Alembic 迁移管理接管。请使用 ./migrate.sh upgrade 执行迁移。
---
添加 subscription_source 字段到 users 表的迁移脚本
"""
from sqlalchemy import text
from config.database import engine


def migrate():
    with engine.connect() as conn:
        try:
            # 检查列是否已存在
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            
            if "subscription_source" not in columns:
                print("正在添加 subscription_source 列...")
                conn.execute(text("ALTER TABLE users ADD COLUMN subscription_source VARCHAR(20)"))
                conn.commit()
                print("✅ 数据库迁移成功！")
            else:
                print("subscription_source 列已存在，无需迁移")
                
        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    migrate()
