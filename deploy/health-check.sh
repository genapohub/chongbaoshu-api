#!/bin/bash
# ============================================================
# 宠宝树 API 健康检查 + 异常告警脚本
# 配合 systemd timer 或 crontab 使用
# ============================================================

set -euo pipefail

# ── 配置区（请按需修改）────────────────────────────────
HEALTH_URL="${HEALTH_URL:-http://localhost:3000/api/health-check}"
TIMEOUT_SEC="${TIMEOUT_SEC:-10}"
MAX_RETRIES="${MAX_RETRIES:-2}"
RETRY_INTERVAL="${RETRY_INTERVAL:-3}"

# 告警 Webhook 地址（二选一，也支持同时配置）
FEISHU_WEBHOOK="${FEISHU_WEBHOOK:-}"
WECOM_WEBHOOK="${WECOM_WEBHOOK:-}"

# 告警标题前缀
ALERT_TITLE="${ALERT_TITLE:-宠宝树 API 服务告警}"
# 服务名称（用于 systemd 管理）
SERVICE_NAME="${SERVICE_NAME:-chongbaoshu-api}"

# 日志文件
CHECK_LOG="/opt/chongbaoshu-api/logs/health-check.log"
# ── 配置区结束 ─────────────────────────────────────────


log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$CHECK_LOG"
}

# 发送飞书告警
send_feishu_alert() {
    local title="$1" content="$2"
    if [ -z "$FEISHU_WEBHOOK" ]; then
        return 1
    fi

    local json_payload
    json_payload=$(cat <<EOF
{
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "$title"
            },
            "template": "red"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "$content"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**时间**: $(date '+%Y-%m-%d %H:%M:%S')\n**主机**: $(hostname)\n**服务**: ${SERVICE_NAME}"
                }
            }
        ]
    }
}
EOF
    )

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$FEISHU_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        --connect-timeout 5 --max-time 10 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        log "[飞书告警] 发送成功"
        return 0
    else
        log "[飞书告警] 发送失败, HTTP $http_code"
        return 1
    fi
}

# 发送企业微信告警
send_wecom_alert() {
    local title="$1" content="$2"
    if [ -z "$WECOM_WEBHOOK" ]; then
        return 1
    fi

    local json_payload
    json_payload=$(cat <<EOF
{
    "msgtype": "markdown",
    "markdown": {
        "content": "## $title\n\n$content\n\n> **时间**: $(date '+%Y-%m-%d %H:%M:%S')\n> **主机**: $(hostname)\n> **服务**: ${SERVICE_NAME}"
    }
}
EOF
    )

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$WECOM_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        --connect-timeout 5 --max-time 10 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        log "[企业微信告警] 发送成功"
        return 0
    else
        log "[企业微信告警] 发送失败, HTTP $http_code"
        return 1
    fi
}

# 发送所有配置的告警通道
send_alert() {
    local title="$1" content="$2"
    local sent=false

    if send_feishu_alert "$title" "$content"; then
        sent=true
    fi

    if send_wecom_alert "$title" "$content"; then
        sent=true
    fi

    if [ "$sent" = false ]; then
        log "[告警] 无可用的告警通道，请检查 FEISHU_WEBHOOK / WECOM_WEBHOOK 环境变量"
    fi
}

# 尝试重启服务
try_restart() {
    log "[服务] 尝试重启 ${SERVICE_NAME}..."
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl restart "$SERVICE_NAME" 2>/dev/null && \
            log "[服务] 重启成功" || \
            log "[服务] 重启失败"
    else
        systemctl start "$SERVICE_NAME" 2>/dev/null && \
            log "[服务] 启动成功" || \
            log "[服务] 启动失败"
    fi
}

# ── 主检查逻辑 ─────────────────────────────────────────
main() {
    # 确保日志目录存在
    mkdir -p "$(dirname "$CHECK_LOG")" 2>/dev/null || true

    local attempt=0
    local last_error=""

    while [ "$attempt" -le "$MAX_RETRIES" ]; do
        attempt=$((attempt + 1))

        # 执行健康检查
        local response http_code body
        response=$(curl -s -w "\n%{http_code}" \
            --connect-timeout "$TIMEOUT_SEC" \
            --max-time "$TIMEOUT_SEC" \
            "$HEALTH_URL" 2>/dev/null) || true

        http_code=$(echo "$response" | tail -1)
        body=$(echo "$response" | head -n -1)

        if [ "$http_code" = "200" ] && echo "$body" | grep -q '"ok"\|"degraded"'; then
            # 服务正常（或降级但存活）
            local status
            status=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ok'))" 2>/dev/null || echo "ok")

            if [ "$status" = "ok" ]; then
                log "[健康检查] 服务正常 ✓ (HTTP $http_code, 尝试 $attempt/$((MAX_RETRIES + 1)))"
                exit 0
            else
                # degraded 状态 - 服务存活但有异常
                log "[健康检查] 服务降级 ⚠ (HTTP $http_code, status=$status)"
                # 提取检查详情
                local checks_detail
                checks_detail=$(echo "$body" | python3 -c "
import sys, json
data = json.load(sys.stdin)
checks = data.get('checks', {})
lines = []
for k, v in checks.items():
    s = v.get('status', 'unknown')
    lines.append(f'- **{k}**: {s}')
    if 'latency_ms' in v:
        lines[-1] += f' (延迟 {v[\"latency_ms\"]}ms)'
    if 'used_percent' in v:
        lines[-1] += f' (使用率 {v[\"used_percent\"]}%)')
print('\n'.join(lines))
" 2>/dev/null || echo "- 详情解析失败")

                send_alert "$ALERT_TITLE - 服务降级" "服务运行中但部分组件异常：\n$checks_detail"
                exit 1
            fi
        fi

        last_error="HTTP $http_code"
        log "[健康检查] 第 $attempt 次检查失败 ($last_error)"

        if [ "$attempt" -le "$MAX_RETRIES" ]; then
            sleep "$RETRY_INTERVAL"
        fi
    done

    # 所有重试均失败
    log "[健康检查] 服务不可用 ✗ ($last_error, 已重试 $MAX_RETRIES 次)"

    # 先尝试重启
    try_restart

    # 等待重启后再次检查
    sleep 5
    local restart_response restart_code
    restart_response=$(curl -s -w "\n%{http_code}" \
        --connect-timeout "$TIMEOUT_SEC" \
        --max-time "$TIMEOUT_SEC" \
        "$HEALTH_URL" 2>/dev/null) || true
    restart_code=$(echo "$restart_response" | tail -1)

    if [ "$restart_code" = "200" ]; then
        send_alert "$ALERT_TITLE - 服务已自动恢复" "服务曾不可用，重启后已恢复正常。"
        log "[健康检查] 重启后服务恢复正常"
        exit 0
    fi

    # 重启后仍不可用，发送严重告警
    send_alert "$ALERT_TITLE - 服务宕机" \
"服务持续不可用，重启后仍未恢复。

**错误**: $last_error
**已重试**: $MAX_RETRIES 次
**重启后状态**: 仍然不可用 (HTTP $restart_code)

请立即排查！"

    log "[健康检查] 服务宕机，告警已发送"
    exit 2
}

main
