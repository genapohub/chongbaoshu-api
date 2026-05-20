#!/usr/bin/env python3
"""数据库迁移脚本：添加缺失的字段"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'chongbaoshu.db')

# 确保data目录存在
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# 如果数据库不存在，先创建
if not os.path.exists(db_path):
    print(f"数据库不存在: {db_path}")
    print("请先启动一次应用以创建数据库")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查 users 表结构
cursor.execute("PRAGMA table_info(users)")
columns = [col[1] for col in cursor.fetchall()]
print(f"当前 users 表字段: {columns}")

# 添加缺失的字段
fields_to_add = []

if 'notify_sms' not in columns:
    fields_to_add.append("ADD COLUMN notify_sms BOOLEAN DEFAULT 0")
    print("添加字段: notify_sms")

if fields_to_add:
    for field in fields_to_add:
        try:
            cursor.execute(f"ALTER TABLE users {field}")
            print(f"成功: {field}")
        except Exception as e:
            print(f"添加字段失败: {field}, 错误: {e}")
    conn.commit()

# 验证
cursor.execute("PRAGMA table_info(users)")
columns = [col[1] for col in cursor.fetchall()]
print(f"更新后 users 表字段: {columns}")

conn.close()
print("数据库迁移完成!")
