#!/bin/bash
# ============================================
# 宠宝树 — 生产环境一键初始化脚本
# 用法：在服务器上以 root 执行
#   chmod +x setup_production.sh
#   ./setup_production.sh
# ============================================
set -e

APP_DIR="/opt/chongbaoshu-api"
APP_USER="www-data"
PYTHON="python3.11"

echo "=== 宠宝树 生产环境初始化 ==="
echo ""

# ── 1. 系统依赖 ──
echo "[1/7] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx sqlite3 curl

# ── 2. 创建应用目录 ──
echo "[2/7] 创建应用目录..."
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/uploads/pets" "$APP_DIR/uploads/kennel"
mkdir -p "$APP_DIR/config/logs"

# ── 3. 复制应用代码 ──
echo "[3/7] 部署应用代码（从 Git 仓库）..."
if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR" && git pull origin master
else
    git clone https://gitee.com/your-org/chongbaoshu-api.git "$APP_DIR"
fi

# ── 4. Python 虚拟环境 ──
echo "[4/7] 创建 Python 虚拟环境..."
cd "$APP_DIR"
$PYTHON -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -q

# ── 5. 环境变量配置 ──
echo "[5/7] 配置环境变量..."
if [ ! -f "$APP_DIR/.env" ]; then
    cat > "$APP_DIR/.env" << 'ENVEOF'
# 宠宝树 生产环境配置
ENV=production

# 数据库 (MySQL)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=chongbaoshu
DB_USER=chongbaoshu
DB_PASS=请替换为强密码

# JWT
JWT_SECRET=请替换为随机64位字符串
JWT_ALGORITHM=HS256

# 微信
WX_APP_ID=你的小程序AppID
WX_APP_SECRET=你的小程序AppSecret

# 微信支付 APIv3
WX_PAY_API_V3_KEY=你的支付密钥

# 文件上传
MAX_UPLOAD_SIZE_MB=5

# 监控
SLOW_REQUEST_THRESHOLD_MS=3000
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
SENTRY_ENV=production
SENTRY_RELEASE=1.1.0
SENTRY_TRACES_SAMPLE_RATE=0.1

# CORS
CORS_ORIGINS=https://api.chongbaoshu.cn

# 开发模式：生产环境务必设为 false
DEV_MODE=false
ENVEOF
    echo "  已生成 .env 模板，请编辑填入真实配置："
    echo "  vim $APP_DIR/.env"
fi

# ── 6. 数据库初始化 ──
echo "[6/7] 数据库初始化..."
cd "$APP_DIR"
source .venv/bin/activate

if [ "$ENV" = "production" ]; then
    # MySQL: 先手动创建库，再执行 Alembic 迁移
    echo "  请确保 MySQL 数据库已创建: CREATE DATABASE chongbaoshu CHARACTER SET utf8mb4;"
    python -m alembic upgrade head
else
    # SQLite: 自动创建
    python -c "
from config.database import Base, engine
from models import *  # noqa: 导入所有模型以注册到 Base.metadata
Base.metadata.create_all(bind=engine)
print('数据库表已创建')
"
fi

# ── 7. Systemd 服务 + Nginx ──
echo "[7/7] 配置 Systemd 服务和 Nginx..."

# Systemd
cp "$APP_DIR/deploy/chongbaoshu-api.service" /etc/systemd/system/
cp "$APP_DIR/deploy/chongbaoshu-api-healthcheck.service" /etc/systemd/system/
cp "$APP_DIR/deploy/chongbaoshu-api-healthcheck.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable chongbaoshu-api
systemctl enable chongbaoshu-api-healthcheck.timer
systemctl start chongbaoshu-api

# Nginx
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/chongbaoshu-api
ln -sf /etc/nginx/sites-available/chongbaoshu-api /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# SSL 证书 (Let's Encrypt)
certbot --nginx -d api.chongbaoshu.cn --non-interactive --agree-tos -m admin@chongbaoshu.cn || echo "  SSL 证书申请需域名已解析，稍后手动执行: certbot --nginx"

echo ""
echo "=== 初始化完成 ==="
echo "检查服务状态: systemctl status chongbaoshu-api"
echo "测试 API: curl https://api.chongbaoshu.cn/api/health-check"
echo ""
echo "⚠️  别忘了编辑 .env 填入真实配置！"
