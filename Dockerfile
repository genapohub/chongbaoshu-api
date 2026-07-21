# ============================================================
#  宠宝树 API — 多阶段构建 Dockerfile
#  Stage 1: 安装依赖（利用缓存层）
#  Stage 2: 运行时镜像（最小化体积）
# ============================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .

# 安装生产依赖
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 运行时阶段 ────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENV=production \
    PORT=3000 \
    TZ=Asia/Shanghai

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

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "3000", \
     "--workers", "2", \
     "--log-level", "info"]
