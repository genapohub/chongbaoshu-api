#!/bin/bash
# ============================================================
#  宠宝树后端 — SQLite 一键部署脚本（与本地开发环境 100% 一致）
#
#  设计原则：线上环境 = 本地开发环境
#    - 数据库用 SQLite（ENV=development），不依赖 MySQL
#    - 不触发生产环境 JWT_SECRET fail-fast
#    - 微信支付/短信/COS/Sentry 均为可选，未配置自动跳过，不报错
#
#  用法（在服务器上项目根目录执行）：
#    bash deploy/deploy_sqlite.sh
#
#  环境要求：Ubuntu/Debian，Python 3.9+（推荐 3.11/3.12）
#    如报 "No module named venv"，先执行：
#    sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
# ============================================================
set -e

# 项目根目录（脚本位于 deploy/ 下）
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

PORT="${PORT:-3000}"
echo "=============================================="
echo "  宠宝树后端 SQLite 一键部署"
echo "  目录: $APP_DIR"
echo "  端口: $PORT"
echo "=============================================="

# ── 1. 检测 Python ──────────────────────────────
echo "[1/7] 检测 Python 解释器..."
# 与 requirements.lock.txt 生成环境一致：本地 .venv 是 3.12，线上也强烈建议 3.12
TARGET_PY="3.12"
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        # 如果找到 3.12，立刻命中；否则保留最先找到的，后续校验版本
        PYTHON="$cmd"
        if $PYTHON --version 2>&1 | grep -q "Python $TARGET_PY"; then
            break
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    echo "❌ 未找到 python3，请先安装 Python 3.9+"
    echo "   sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip"
    exit 1
fi
PY_VER=$($PYTHON --version 2>&1)
echo "  使用 $PYTHON（$PY_VER）"
if ! echo "$PY_VER" | grep -q "Python $TARGET_PY"; then
    echo "  ⚠️  警告：当前 Python 不是 $TARGET_PY（锁文件由 Python $TARGET_PY 生成）"
    echo "  建议先安装 Python $TARGET_PY 以获得与本地开发一致的运行环境。"
    echo "  本次部署继续，但如遇 ABI/依赖问题，请切换到 Python $TARGET_PY 重试。"
fi

# ── 2. 虚拟环境 + 依赖 ─────────────────────────
echo "[2/7] 准备虚拟环境..."
VENV_PY_VERSION=""
if [ -d ".venv" ]; then
    VENV_PY_VERSION=$(.venv/bin/python --version 2>&1 || echo "unknown")
fi
# 如果 venv 已存在但 Python 版本与目标不一致，重建（避免 uv/conda 等工具创建的无 pip venv 导致部署失败）
if [ -d ".venv" ] && ! echo "$VENV_PY_VERSION" | grep -q "Python $TARGET_PY"; then
    echo "  现有 .venv 版本 $VENV_PY_VERSION 与目标 $TARGET_PY 不一致，重建..."
    rm -rf .venv
fi
if [ ! -d ".venv" ]; then
    if ! "$PYTHON" -m venv .venv 2>/dev/null; then
        echo "❌ 创建 venv 失败，请安装 python3-venv："
        echo "   sudo apt-get install -y python3-venv"
        exit 1
    fi
fi
# 兼容 uv/poetry 等工具创建的 venv（不一定有 .venv/bin/pip），统一用 python -m pip
PIP_CMD=".venv/bin/python -m pip"
if ! $PIP_CMD --version >/dev/null 2>&1; then
    echo "  venv 中未找到 pip，尝试 bootstrap..."
    .venv/bin/python -m ensurepip -q 2>/dev/null || {
        echo "❌ 无法为 venv 安装 pip，请确保系统 python 包含 ensurepip"
        exit 1
    }
fi
# 说明：使用 requirements.lock.txt（全量锁定，含传递依赖），
#       保证线上与本发环境逐包逐版本一致；缺失时回退 requirements.txt。
if [ -f "requirements.lock.txt" ]; then
  REQ="requirements.lock.txt"
else
  echo "  ⚠️  未找到 requirements.lock.txt，回退 requirements.txt（存在依赖漂移风险）"
  REQ="requirements.txt"
fi
echo "  安装依赖: $REQ （首次约 1-2 分钟）..."
# 国内服务器可取消下一行注释，改用清华镜像加速
# PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
$PIP_CMD install -r "$REQ" -q ${PIP_INDEX:+-i $PIP_INDEX} 2>/dev/null \
  || $PIP_CMD install -r "$REQ" -q
echo "  依赖安装完成"

# ── 3. 生成 .env（SQLite + 随机 JWT_SECRET）────
echo "[3/7] 配置环境变量..."
if [ ! -f ".env" ]; then
    SECRET=$(.venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
    cat > .env <<EOF
# 宠宝树后端 — SQLite 一致模式（由 deploy_sqlite.sh 生成）
PORT=$PORT
ENV=development
DEV_MODE=true
JWT_SECRET=$SECRET
JWT_ALGORITHM=HS256

# 数据库（SQLite，与本地开发一致）
DB_STORAGE=./database.sqlite

# 微信小程序（如已申请，请填真实值）
WX_APP_ID=your_app_id
WX_APP_SECRET=your_app_secret

# CORS（如需限制来源，改为具体域名）
CORS_ORIGINS=*
EOF
    echo "  已生成 .env（JWT_SECRET 已随机化，SQLite 模式）"
else
    echo "  .env 已存在，跳过（如需重置请删除后重跑）"
fi

# ── 4. 数据目录 ─────────────────────────────────
echo "[4/7] 创建数据目录..."
mkdir -p uploads/pets uploads/kennel logs config/logs
echo "  目录就绪"

# ── 5. 启动前配置校验（失败即退出，避免带病上线）──
echo "[5/7] 启动前配置校验..."
if [ -f "deploy/preflight.py" ]; then
  .venv/bin/python deploy/preflight.py || {
    echo "❌ 配置校验未通过，已中止部署（请先按上方提示修复）"
    exit 1
  }
else
  echo "  ⚠️  未找到 deploy/preflight.py，跳过校验"
  .venv/bin/python -c "from main import app; print('  应用导入 OK:', app.title)" \
    || { echo "❌ 应用导入失败，请检查上方错误"; exit 1; }
fi

# ── 6. 启动服务 ─────────────────────────────────
echo "[6/7] 启动服务..."
if [ -f ".dev-server.pid" ]; then
    OLD_PID=$(cat .dev-server.pid)
    kill "$OLD_PID" 2>/dev/null && echo "  已停止旧进程 (PID: $OLD_PID)" || true
    rm -f .dev-server.pid
    sleep 1
fi

nohup .venv/bin/python -m uvicorn main:app \
    --host 0.0.0.0 --port "$PORT" \
    > logs/server.log 2>&1 &
echo $! > .dev-server.pid

sleep 3
echo ""
echo "=============================================="
echo "  [7/7] 验证服务..."
echo "=============================================="
# curl 需绕过可能的 http_proxy，否则访问 127.0.0.1 会被代理拦截
CURL="curl -s --noproxy *"
if $CURL -f --max-time 10 "http://127.0.0.1:$PORT/api/health-check" >/dev/null 2>&1; then
    echo "✅ 简单健康检查通过:"
    $CURL --max-time 10 "http://127.0.0.1:$PORT/api/health-check"
    echo ""
    echo "✅ 深度健康检查:"
    $CURL --max-time 25 "http://127.0.0.1:$PORT/api/health-check/deep"
    echo ""
    echo ""
    echo "部署成功！"
    echo "  服务地址: http://<服务器IP>:$PORT"
    echo "  健康检查: http://<服务器IP>:$PORT/api/health-check"
    echo "  进程 PID: $(cat .dev-server.pid)"
    echo "  运行日志: tail -f logs/server.log"
    echo "  停止服务: kill $(cat .dev-server.pid)"
else
    echo "❌ 服务启动失败，请查看日志:"
    echo "   tail -50 logs/server.log"
    exit 1
fi
