"""
[已废弃] 此脚本已被 Alembic 迁移管理接管。
对应的迁移已包含在 migrations/versions/20260525_1507-*_sync_schema_add_indexes_fix_types.py 中。
请使用 ./migrate.sh upgrade 来执行迁移，勿再直接运行此脚本。
---
生产环境 FK 索引迁移脚本
用法：python migrate_add_fk_indexes.py

为所有外键列添加显式索引，提升查询性能。
SQLite 下 FK 列不自动建索引，MySQL 也推荐显式声明。
"""

from config.database import engine
from sqlalchemy import text


INDEXES = [
    ("ix_pets_owner_id", "pets", "owner_id"),
    ("ix_breeding_records_owner_id", "breeding_records", "owner_id"),
    ("ix_breeding_records_mother_id", "breeding_records", "mother_id"),
    ("ix_health_records_pet_id", "health_records", "pet_id"),
    ("ix_health_records_owner_id", "health_records", "owner_id"),
    ("ix_notifications_user_id", "notifications", "user_id"),
    ("ix_pet_photos_pet_id", "pet_photos", "pet_id"),
    ("ix_pet_tags_pet_id", "pet_tags", "pet_id"),
    ("ix_invite_records_inviter_id", "invite_records", "inviter_id"),
    ("ix_export_tasks_user_id", "export_tasks", "user_id"),
    ("ix_subscription_orders_user_id", "subscription_orders", "user_id"),
]


def migrate():
    print("开始 FK 索引迁移...")
    with engine.connect() as conn:
        for idx_name, table, column in INDEXES:
            try:
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})"
                ))
                print(f"  ✅ Created index {idx_name}")
            except Exception as e:
                print(f"  ⚠️ Index {idx_name} may already exist: {e}")
        conn.commit()
    print("迁移完成！")


if __name__ == "__main__":
    migrate()
