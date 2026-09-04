#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宠宝树 API — 启动前配置校验（preflight）

设计目的
--------
把「线上运行到一半才报错」提前为「启动前一次性明确报错」。
部署脚本应在启动 uvicorn 之前调用本脚本；任一 FATAL 校验失败即退出码 1，
避免带着错误配置上线、产生难以定位的运行时异常。

用法
----
    .venv/bin/python deploy/preflight.py            # 校验后打印结论
    .venv/bin/python deploy/preflight.py --strict   # 警告也视为失败（CI 用）

退出码
------
    0  全部通过（可有 WARNING）
    1  存在 FATAL 错误（--strict 时 WARNING 也导致 1）
"""

import os
import sys
import stat
import socket
from pathlib import Path

# 让脚本能 import 项目根目录下的 config / main
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

os.chdir(APP_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

FATAL = []
WARN = []
OK = []

# 本地已验证通过的 Python 版本（见 .venv，改动需同步这里）
VERIFIED_PY = (3, 12)


def fatal(msg, fix=""):
    FATAL.append((msg, fix))


def warn(msg, fix=""):
    WARN.append((msg, fix))


def ok(msg):
    """记录通过项，并立即回显，便于部署时直观看进度"""
    OK.append(msg)
    print(f"  ✅ {msg}")


def hr(title):
    print(f"\n── {title} " + "─" * max(0, 56 - len(title)))


# ── 1. Python 版本 ────────────────────────────────────────
def check_python():
    hr("Python 运行时")
    v = sys.version_info
    cur = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) < (3, 9):
        fatal(f"Python {cur} 过低，项目要求 >= 3.9", "升级到 Python 3.12（与本地开发一致）")
        return
    if (v.major, v.minor) != VERIFIED_PY:
        warn(
            f"当前 Python {cur}，本地已验证版本为 {VERIFIED_PY[0]}.{VERIFIED_PY[1]}",
            "建议统一到 3.12，避免版本差异导致的行为不一致",
        )
    else:
        ok(f"Python {cur}（与本地验证版本一致）")


# ── 2. 依赖完整性 ─────────────────────────────────────────
def check_dependencies():
    hr("依赖完整性")
    required = [
        "fastapi", "uvicorn", "sqlalchemy", "pydantic", "jose",
        "slowapi", "sentry_sdk", "bleach", "dotenv", "requests",
        "aiofiles", "multipart", "alembic",
    ]
    missing = []
    for mod in required:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        fatal(
            f"缺少依赖: {', '.join(missing)}",
            "执行 .venv/bin/pip install -r requirements.lock.txt",
        )
    else:
        ok(f"{len(required)} 个核心依赖全部可导入")

    # 数据库驱动按方言检查
    dialect = os.getenv("DB_DIALECT", "sqlite").lower()
    if dialect == "mysql" or os.getenv("ENV") == "production":
        try:
            __import__(("pymysql"))
            ok("MySQL 驱动 pymysql 已安装")
        except ImportError:
            fatal("生产/MySQL 模式缺少 pymysql", "pip install pymysql")


# ── 3. JWT 密钥 ───────────────────────────────────────────
def check_jwt():
    hr("安全配置")
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        fatal("JWT_SECRET 未设置", "在 .env 中设置 JWT_SECRET（建议 secrets.token_hex(32)）")
        return
    if secret in ("your-secret-key", "changeme", "secret", "test"):
        fatal("JWT_SECRET 仍是占位符", "必须替换为随机高强度密钥")
        return
    if len(secret) < 32:
        warn(f"JWT_SECRET 仅 {len(secret)} 字符，强度不足", "建议 >= 32 字符（64 位十六进制）")
    else:
        ok(f"JWT_SECRET 已设置（{len(secret)} 字符）")

    if os.getenv("ENV") == "production" and os.getenv("CORS_ORIGINS", "*") == "*":
        warn("生产环境 CORS_ORIGINS=*，任意站点可调用接口", "改为具体域名，逗号分隔")
    elif os.getenv("CORS_ORIGINS"):
        ok(f"CORS_ORIGINS={os.getenv('CORS_ORIGINS')}")


# ── 4. 数据库 ─────────────────────────────────────────────
def check_database():
    hr("数据库")
    env = os.getenv("ENV", "development")
    try:
        from config.env import get_db_url, is_production
        url = get_db_url()
    except Exception as e:
        fatal(f"解析数据库配置失败: {e}", "检查 config/env.py 与 DB_* 环境变量")
        return

    masked = url.split("@")[-1] if "@" in url else url
    print(f"  ENV={env}  连接={masked}")

    if url.startswith("sqlite"):
        # 取出文件路径：sqlite:///./database.sqlite
        path = url.replace("sqlite:///", "")
        p = Path(path)
        parent = p.parent if str(p.parent) not in ("", ".") else Path(".")
        if not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True)
                ok(f"已创建数据库目录 {parent}")
            except Exception as e:
                fatal(f"数据库目录 {parent} 无法创建: {e}", "检查磁盘权限")
                return
        # 目录可写
        if not os.access(str(parent), os.W_OK):
            fatal(f"数据库目录 {parent} 不可写", f"chown -R $(whoami) {parent}")
            return
        # 已存在则检查读写
        if p.exists() and not os.access(str(p), os.W_OK):
            fatal(f"数据库文件 {p} 不可写", f"chmod 664 {p}")
            return
        # 真实连通性探测
        try:
            import sqlite3
            con = sqlite3.connect(str(p), timeout=5)
            con.execute("SELECT 1").fetchone()
            con.close()
            ok(f"SQLite 可读写（{p}）")
        except Exception as e:
            fatal(f"SQLite 连接失败: {e}", "检查文件路径与磁盘权限")
            return
        if is_production():
            warn("生产环境使用 SQLite，并发写入能力有限", "用户量上来后迁移 MySQL")
    else:
        # MySQL 连通性探测
        try:
            import pymysql
            from urllib.parse import urlparse
            u = urlparse(url.replace("mysql+pymysql://", "mysql://"))
            con = pymysql.connect(
                host=u.hostname, port=u.port or 3306,
                user=u.username, password=u.password,
                database=u.path.lstrip("/"), connect_timeout=5,
            )
            con.close()
            ok(f"MySQL 连通（{u.hostname}:{u.port or 3306}）")
        except Exception as e:
            fatal(f"MySQL 连接失败: {e}", "检查 DB_HOST/DB_PORT/DB_USER/DB_PASS 与网络策略")


# ── 5. 目录可写 ───────────────────────────────────────────
def check_directories():
    hr("目录权限")
    dirs = ["uploads", "logs", "data"]
    for d in dirs:
        p = Path(d)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            fatal(f"目录 {d} 创建失败: {e}", "检查磁盘权限")
            continue
        if not os.access(str(p), os.W_OK):
            fatal(f"目录 {d} 不可写", f"chown -R $(whoami) {d}")
        else:
            ok(f"{d}/ 可写")


# ── 6. 微信配置 ───────────────────────────────────────────
def check_wechat():
    hr("微信配置")
    app_id = os.getenv("WX_APP_ID", "")
    app_secret = os.getenv("WX_APP_SECRET", "")
    placeholders = {"", "your_app_id", "your-app-id", "xxx"}
    if app_id in placeholders or app_secret in placeholders:
        warn(
            "WX_APP_ID / WX_APP_SECRET 仍是占位符，微信登录将失败",
            "小程序后台获取后填入 .env（不影响服务启动，但登录功能不可用）",
        )
    else:
        ok(f"WX_APP_ID 已配置（{app_id[:8]}…）")


# ── 7. 端口 ───────────────────────────────────────────────
def check_port():
    hr("端口占用")
    port = int(os.getenv("PORT", "3000"))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port))
        ok(f"端口 {port} 可用")
    except OSError:
        warn(
            f"端口 {port} 已被占用",
            "若为旧实例请先停止（kill $(cat .dev-server.pid)），或换 PORT",
        )
    finally:
        s.close()


# ── 8. 应用可导入 ─────────────────────────────────────────
def check_app_import():
    hr("应用导入")
    try:
        from main import app  # noqa: F401
        routes = len(app.routes)
        ok(f"main:app 导入成功（{routes} 条路由）")
    except Exception as e:
        import traceback
        fatal(f"应用导入失败: {type(e).__name__}: {e}", "查看上方 traceback 修复后重试")
        traceback.print_exc()


def main():
    print("=" * 64)
    print("  宠宝树 API — 启动前配置校验")
    print(f"  目录: {APP_DIR}")
    print("=" * 64)

    check_python()
    check_dependencies()
    check_jwt()
    check_database()
    check_directories()
    check_wechat()
    check_port()
    check_app_import()

    print("\n" + "=" * 64)
    print(f"  通过 {len(OK)}   警告 {len(WARN)}   致命 {len(FATAL)}")
    print("=" * 64)

    if WARN:
        print("\n⚠️  警告（不阻断启动，但建议处理）：")
        for m, fix in WARN:
            print(f"  • {m}")
            if fix:
                print(f"      → {fix}")

    if FATAL:
        print("\n❌ 致命错误（已阻断启动）：")
        for m, fix in FATAL:
            print(f"  • {m}")
            if fix:
                print(f"      → {fix}")
        print("\n修复后重新运行：.venv/bin/python deploy/preflight.py")
        return 1

    strict = "--strict" in sys.argv
    if strict and WARN:
        print("\n❌ --strict 模式：存在警告，视为失败")
        return 1

    print("\n✅ 配置校验通过，可以启动服务")
    return 0


if __name__ == "__main__":
    sys.exit(main())
