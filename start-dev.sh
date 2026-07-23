#!/bin/bash
# 宠宝树后端 - 开发环境启动脚本
# 自动重启：代码改动时 uvicorn --reload 会自动重载
# 常驻运行：nohup 确保终端关闭后不挂掉
# 日志输出：./logs/dev-server.log
# 使用方法：bash start-dev.sh

API_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$API_DIR/logs"
PID_FILE="$API_DIR/.dev-server.pid"
PYTHON="/Users/macos/.workbuddy/binaries/python/envs/default/bin/python"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 杀掉旧进程
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "正在停止旧服务 (PID: $OLD_PID)..."
        kill "$OLD_PID"
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

# 启动服务（--reload 自动检测代码变更并重启）
cd "$API_DIR"
nohup "$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port 8081 --reload --log-level info \
    > "$LOG_DIR/dev-server.log" 2>&1 &

# 记录 PID
echo $! > "$PID_FILE"

echo "✅ 宠宝树后端已启动"
echo "  地址: http://localhost:8081"
echo "  健康检查: http://localhost:8081/api/health-check"
echo "  日志: $LOG_DIR/dev-server.log"
echo "  PID: $(cat $PID_FILE)"
echo ""
echo "  💡 代码改动后自��重启（--reload 生效中）"
echo "  停止服务: kill $(cat $PID_FILE)"
