# ============================================================
#  宠宝树 API — 多阶段构建 Dockerfile
#  Stage 1: 安装依赖（利用缓存层）
#  Stage 2: 运行时镜像（最小化体积）
# ============================================================

# Python 版本必须与本地开发一致（本地 .venv 为 3.12，见 requirements.lock.txt 头部）
# 版本不一致是「本地能跑、线上报错」最常见的根因之一
FROM python:3.12-slim AS builder

WORKDIR /app

# 复制依赖清单（锁文件优先，保证与本地逐包逐版本一致）
COPY requirements.lock.txt requirements.txt ./

# 安装依赖到独立前缀，供运行时阶段复制
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock.txt

# ── 运行时阶段 ────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# 说明：ENV 默认设为 docker（SQLite），与本地开发环境一致。
#   - docker   → SQLite，零外部依赖，行为等同本地开发
#   - production → 需配置 DB_HOST/DB_NAME/DB_USER/DB_PASS 走 MySQL，
#                  并启用微信模板推送 / 短信（见 config/env.py）
#   切换方式：docker run -e ENV=production ... 或在 compose 的 environment 覆盖
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENV=docker \
    PORT=3000 \
    TZ=Asia/Shanghai \
    DB_STORAGE=/opt/chongbaoshu-api/database/database.sqlite

# 安装运行时依赖（sqlite 工具等）
RUN apt-get update && \
    apt-get install -y --no-install-recommends sqlite3 curl && \
    rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制已安装的包
COPY --from=builder /install /usr/local

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /opt/chongbaoshu-api

# 复制应用代码
COPY --chown=appuser:appuser . .

# 创建必要的目录
RUN mkdir -p /opt/chongbaoshu-api/uploads \
             /opt/chongbaoshu-api/logs \
             /opt/chongbaoshu-api/certs \
             /opt/chongbaoshu-api/database && \
    chown -R appuser:appuser /opt/chongbaoshu-api

USER appuser

EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/api/health-check || exit 1

# 启动流程：先跑配置校验（失败即退出，避免带病上线），再拉起服务。
# 关于 workers：SQLite 模式下多进程并发写容易产生 "database is locked"，
#   故默认 1 个 worker（与本地开发 uvicorn 默认行为一致）；
#   若切到 MySQL（ENV=production），可通过 UVICORN_WORKERS 调大。
CMD ["sh", "-c", "\
     python deploy/preflight.py && \
     exec uvicorn main:app \
       --host 0.0.0.0 \
       --port ${PORT:-3000} \
       --workers ${UVICORN_WORKERS:-1} \
       --log-level info"]
