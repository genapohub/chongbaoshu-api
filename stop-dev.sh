#!/bin/bash
# 停止开发服务
API_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$API_DIR/.dev-server.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        rm -f "$PID_FILE"
        echo "✅ 已停止 (PID: $PID)"
    else
        rm -f "$PID_FILE"
        echo "⚠️  PID 文件存在但进程已不存在，已清理"
    fi
else
    # fallback: kill by port
    PID=$(lsof -ti:8081 2>/dev/null)
    if [ -n "$PID" ]; then
        kill "$PID"
        echo "✅ 已停止 8081 端口进程 (PID: $PID)"
    else
        echo "⚠️  没有运行中的服务"
    fi
fi
