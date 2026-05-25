"""sync_schema_add_indexes_fix_types

Revision ID: 267ea23d9b0d
Revises: 14f1ce0042b5
Create Date: 2026-05-25 15:07:19.070904

手工调整说明：
1. 所有 create_index 改为 IF NOT EXISTS（历史手动脚本已建过部分索引）
2. create_unique_constraint 补充显式名称（SQLite batch 模式要求）
3. drop_table feedbacks 加防御判断（表可能已被手动删除）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = '267ea23d9b0d'
down_revision: Union[str, None] = '14f1ce0042b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    """检查索引是否已存在（SQLite 专用）"""
    result = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='index' AND name=:n"),
        {"n": index_name},
    )
    return result.fetchone() is not None


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": table_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 删除废弃的 feedbacks 表（如果还在的话）
    if _table_exists(conn, 'feedbacks'):
        op.drop_table('feedbacks')

    # 2. breeding_records FK 索引
    with op.batch_alter_table('breeding_records', schema=None) as batch_op:
        if not _index_exists(conn, 'breeding_records', 'ix_breeding_records_mother_id'):
            batch_op.create_index(batch_op.f('ix_breeding_records_mother_id'), ['mother_id'], unique=False)
        if not _index_exists(conn, 'breeding_records', 'ix_breeding_records_owner_id'):
            batch_op.create_index(batch_op.f('ix_breeding_records_owner_id'), ['owner_id'], unique=False)

    # 3. export_tasks FK 索引
    with op.batch_alter_table('export_tasks', schema=None) as batch_op:
        if not _index_exists(conn, 'export_tasks', 'ix_export_tasks_user_id'):
            batch_op.create_index(batch_op.f('ix_export_tasks_user_id'), ['user_id'], unique=False)

    # 4. health_records FK 索引
    with op.batch_alter_table('health_records', schema=None) as batch_op:
        if not _index_exists(conn, 'health_records', 'ix_health_records_owner_id'):
            batch_op.create_index(batch_op.f('ix_health_records_owner_id'), ['owner_id'], unique=False)
        if not _index_exists(conn, 'health_records', 'ix_health_records_pet_id'):
            batch_op.create_index(batch_op.f('ix_health_records_pet_id'), ['pet_id'], unique=False)

    # 5. invite_records FK 索引
    with op.batch_alter_table('invite_records', schema=None) as batch_op:
        if not _index_exists(conn, 'invite_records', 'ix_invite_records_inviter_id'):
            batch_op.create_index(batch_op.f('ix_invite_records_inviter_id'), ['inviter_id'], unique=False)

    # 6. notifications FK 索引
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        if not _index_exists(conn, 'notifications', 'ix_notifications_user_id'):
            batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)

    # 7. pedigree_certificates: TEXT -> JSON
    with op.batch_alter_table('pedigree_certificates', schema=None) as batch_op:
        batch_op.alter_column('pedigree_tree',
               existing_type=sa.TEXT(),
               type_=sa.JSON(),
               existing_nullable=True)

    # 8. pet_photos FK 索引
    with op.batch_alter_table('pet_photos', schema=None) as batch_op:
        if not _index_exists(conn, 'pet_photos', 'ix_pet_photos_pet_id'):
            batch_op.create_index(batch_op.f('ix_pet_photos_pet_id'), ['pet_id'], unique=False)

    # 9. pet_tags FK 索引
    with op.batch_alter_table('pet_tags', schema=None) as batch_op:
        if not _index_exists(conn, 'pet_tags', 'ix_pet_tags_pet_id'):
            batch_op.create_index(batch_op.f('ix_pet_tags_pet_id'), ['pet_id'], unique=False)

    # 10. pets: role TEXT -> String(20), 替换 platform_cert_no 约束, owner_id 索引
    with op.batch_alter_table('pets', schema=None) as batch_op:
        batch_op.alter_column('role',
               existing_type=sa.TEXT(),
               type_=sa.String(length=20),
               existing_nullable=True)
        # 删除手动创建的 partial index（WHERE IS NOT NULL），换成标准 UniqueConstraint
        if _index_exists(conn, 'pets', 'ix_pets_platform_cert_no'):
            batch_op.drop_index('ix_pets_platform_cert_no')
        if not _index_exists(conn, 'pets', 'uq_pets_platform_cert_no'):
            batch_op.create_unique_constraint('uq_pets_platform_cert_no', ['platform_cert_no'])
        if not _index_exists(conn, 'pets', 'ix_pets_owner_id'):
            batch_op.create_index(batch_op.f('ix_pets_owner_id'), ['owner_id'], unique=False)

    # 11. subscription_orders FK 索引
    with op.batch_alter_table('subscription_orders', schema=None) as batch_op:
        if not _index_exists(conn, 'subscription_orders', 'ix_subscription_orders_user_id'):
            batch_op.create_index(batch_op.f('ix_subscription_orders_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table('subscription_orders', schema=None) as batch_op:
        if _index_exists(conn, 'subscription_orders', 'ix_subscription_orders_user_id'):
            batch_op.drop_index(batch_op.f('ix_subscription_orders_user_id'))

    with op.batch_alter_table('pets', schema=None) as batch_op:
        batch_op.drop_constraint('uq_pets_platform_cert_no', type_='unique')
        if _index_exists(conn, 'pets', 'ix_pets_owner_id'):
            batch_op.drop_index(batch_op.f('ix_pets_owner_id'))
        batch_op.create_index('ix_pets_platform_cert_no', ['platform_cert_no'], unique=True,
                               sqlite_where=sa.text('platform_cert_no IS NOT NULL'))
        batch_op.alter_column('role',
               existing_type=sa.String(length=20),
               type_=sa.TEXT(),
               existing_nullable=True)

    with op.batch_alter_table('pet_tags', schema=None) as batch_op:
        if _index_exists(conn, 'pet_tags', 'ix_pet_tags_pet_id'):
            batch_op.drop_index(batch_op.f('ix_pet_tags_pet_id'))

    with op.batch_alter_table('pet_photos', schema=None) as batch_op:
        if _index_exists(conn, 'pet_photos', 'ix_pet_photos_pet_id'):
            batch_op.drop_index(batch_op.f('ix_pet_photos_pet_id'))

    with op.batch_alter_table('pedigree_certificates', schema=None) as batch_op:
        batch_op.alter_column('pedigree_tree',
               existing_type=sa.JSON(),
               type_=sa.TEXT(),
               existing_nullable=True)

    with op.batch_alter_table('notifications', schema=None) as batch_op:
        if _index_exists(conn, 'notifications', 'ix_notifications_user_id'):
            batch_op.drop_index(batch_op.f('ix_notifications_user_id'))

    with op.batch_alter_table('invite_records', schema=None) as batch_op:
        if _index_exists(conn, 'invite_records', 'ix_invite_records_inviter_id'):
            batch_op.drop_index(batch_op.f('ix_invite_records_inviter_id'))

    with op.batch_alter_table('health_records', schema=None) as batch_op:
        if _index_exists(conn, 'health_records', 'ix_health_records_pet_id'):
            batch_op.drop_index(batch_op.f('ix_health_records_pet_id'))
        if _index_exists(conn, 'health_records', 'ix_health_records_owner_id'):
            batch_op.drop_index(batch_op.f('ix_health_records_owner_id'))

    with op.batch_alter_table('export_tasks', schema=None) as batch_op:
        if _index_exists(conn, 'export_tasks', 'ix_export_tasks_user_id'):
            batch_op.drop_index(batch_op.f('ix_export_tasks_user_id'))

    with op.batch_alter_table('breeding_records', schema=None) as batch_op:
        if _index_exists(conn, 'breeding_records', 'ix_breeding_records_owner_id'):
            batch_op.drop_index(batch_op.f('ix_breeding_records_owner_id'))
        if _index_exists(conn, 'breeding_records', 'ix_breeding_records_mother_id'):
            batch_op.drop_index(batch_op.f('ix_breeding_records_mother_id'))

    op.create_table('feedbacks',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('user_id', sa.INTEGER(), nullable=False),
        sa.Column('content', sa.TEXT(), nullable=False),
        sa.Column('contact', sa.VARCHAR(length=100), nullable=True),
        sa.Column('created_at', sa.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
