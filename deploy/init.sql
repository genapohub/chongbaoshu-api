-- ============================================================
--  宠宝树 — MySQL 生产环境初始化 SQL
--  首次部署时执行，创建数据库和基础表结构
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS chongbaoshu CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE chongbaoshu;

-- 核心表由 Alembic 自动创建，此处仅作初始检查和索引优化
-- 执行 alembic upgrade head 完成首次迁移

SET FOREIGN_KEY_CHECKS = 1;

SELECT '数据库初始化完成。请执行: alembic upgrade head' AS status;
