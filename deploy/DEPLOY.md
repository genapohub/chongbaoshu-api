# 宠宝树 API 部署运维指南

## 目录

- [架构概览](#架构概览)
- [1. 服务器部署](#1-服务器部署)
- [2. systemd 进程守护](#2-systemd-进程守护)
- [3. 日志管理](#3-日志管理)
- [4. 健康检查](#4-健康检查)
- [5. 异常告警](#5-异常告警)
- [6. 日常运维](#6-日常运维)
- [7. 故障排查](#7-故障排查)

---

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│                   systemd                           │
│  ┌─────────────────┐    ┌─────────────────────────┐ │
│  │ chongbaoshu-api │    │ health-check.timer      │ │
│  │   .service      │    │   (每60秒)               │ │
│  │  (uvicorn x2)   │    │         │                │ │
│  └────────┬────────┘    └─────────┼───────────────┘ │
│           │                       │                  │
│           ▼                       ▼                  │
│  ┌─────────────────┐    ┌─────────────────────────┐ │
│  │  logs/          │    │ health-check.sh         │ │
│  │  ├ access.log   │    │  ├ 飞书 Webhook 通知     │ │
│  │  ├ error.log    │    │  └ 企业微信 Webhook 通知 │ │
│  │  └ health-check │    └─────────────────────────┘ │
│  │       .log       │                               │
│  └────────┬────────┘                                │
│           │ logrotate (每日轮转)                      │
└───────────┼──────────────────────────────────────────┘
            ▼
┌───────────────────────┐
│  Nginx (反向代理)      │
│  :80 → :443 → :3000   │
└───────────────────────┘
```

---

## 1. 服务器部署

### 1.1 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Ubuntu 20.04+ / CentOS 8+ / Debian 11+ |
| Python | 3.9+ |
| 内存 | ≥ 1GB（推荐 2GB） |
| 磁盘 | ≥ 10GB（日志和数据文件） |

### 1.2 首次部署

```bash
# 1. 创建服务用户
sudo useradd -r -s /bin/false www-data 2>/dev/null || true

# 2. 创建项目目录
sudo mkdir -p /opt/chongbaoshu-api
sudo chown www-data:www-data /opt/chongbaoshu-api

# 3. 上传项目代码
# 方式 A: Git clone
cd /opt && sudo git clone <your-repo-url> chongbaoshu-api
# 方式 B: 直接上传文件

# 4. 创建虚拟环境 & 安装依赖
cd /opt/chongbaoshu-api
sudo python3 -m venv venv
sudo venv/bin/pip install --no-cache-dir -r requirements.txt

# 5. 配置环境变量
sudo cp .env.example .env
sudo vim .env  # 编辑生产环境配置

# 6. 创建日志目录
sudo mkdir -p logs
sudo chown www-data:www-data logs

# 7. 初始化数据库
sudo -u www-data venv/bin/python -c "from main import app; print('OK')"
```

### 1.3 生产环境 `.env` 配置要点

```env
# 必须改为 production
ENV=production
DEV_MODE=false

# 监听端口（systemd 管理时固定 3000）
PORT=3000

# JWT 密钥（生产环境务必更换为随机强密钥）
# 生成方式: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=<64位随机hex字符串>

# 数据库（生产环境建议使用 MySQL）
DB_DIALECT=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=chongbaoshu
DB_USER=chongbaoshu
DB_PASS=<强密码>

# CORS（限制为你的域名）
CORS_ORIGINS=https://chongbaoshu.com,https://api.chongbaoshu.com

# 告警 Webhook（用于 health-check.sh）
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
# 或者企业微信
WECOM_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

---

## 2. systemd 进程守护

### 2.1 安装服务

```bash
# 复制 service 文件
sudo cp deploy/chongbaoshu-api.service /etc/systemd/system/

# 加载配置
sudo systemctl daemon-reload

# 启用开机自启
sudo systemctl enable chongbaoshu-api

# 启动服务
sudo systemctl start chongbaoshu-api

# 查看状态
sudo systemctl status chongbaoshu-api
```

### 2.2 关键参数说明

| 参数 | 值 | 说明 |
|------|----|------|
| `Restart=always` | - | 进程退出后自动重启 |
| `RestartSec=5` | 5s | 重启间隔 5 秒 |
| `StartLimitBurst=5` | 5次 | 300s 内最多重启 5 次 |
| `LimitNOFILE=65536` | - | 最大文件描述符数 |
| `workers=2` | 2个 | uvicorn worker 进程数 |
| `ProtectSystem=strict` | - | 文件系统保护 |
| `ReadWritePaths` | uploads/logs | 仅允许写入的目录 |

### 2.3 重启策略

- **正常退出**（SIGTERM）→ 5 秒后自动重启
- **崩溃退出**（非零退出码）→ 5 秒后自动重启
- **5分钟内重启超过5次** → 停止重启，需手动 `systemctl reset-failed`
- **优雅停止**：发送 SIGTERM → 等待 30 秒 → 强制 SIGKILL

### 2.4 服务管理命令

```bash
# 启停
sudo systemctl start chongbaoshu-api    # 启动
sudo systemctl stop chongbaoshu-api     # 停止
sudo systemctl restart chongbaoshu-api  # 重启
sudo systemctl reload chongbaoshu-api   # 平滑重载（不支持，需 restart）

# 状态
sudo systemctl status chongbaoshu-api   # 详细状态
sudo systemctl is-active chongbaoshu-api  # 是否运行

# 日志
sudo journalctl -u chongbaoshu-api -f         # 实时日志
sudo journalctl -u chongbaoshu-api --since today  # 今日日志
sudo journalctl -u chongbaoshu-api -n 100      # 最近100行
```

---

## 3. 日志管理

### 3.1 日志文件说明

| 文件 | 内容 | 轮转策略 |
|------|------|----------|
| `logs/access.log` | 所有 HTTP 请求（方法、路径、状态码、耗时） | 每日轮转，保留 30 天 |
| `logs/error.log` | 所有 ERROR 级别日志 | 每日轮转，保留 90 天 |
| `logs/stdout.log` | uvicorn 标准输出 | logrotate，保留 30 天 |
| `logs/stderr.log` | uvicorn 标准错误 | logrotate，保留 30 天 |
| `logs/health-check.log` | 健康检查结果 | 手动管理 |

### 3.2 日志格式

```
# access.log
2026-05-24 16:00:00 INFO access GET /api/pets → 200 (12.3ms)

# error.log
2026-05-24 16:00:01 ERROR error HTTP POST /api/auth/login → 401 (code=1002, detail=用户名或密码错误)
```

### 3.3 配置 logrotate

```bash
# 复制 logrotate 配置
sudo cp deploy/chongbaoshu-api.logrotate /etc/logrotate.d/chongbaoshu-api

# 测试配置
sudo logrotate -d /etc/logrotate.d/chongbaoshu-api

# 手动触发轮转
sudo logrotate -f /etc/logrotate.d/chongbaoshu-api
```

### 3.4 查看日志

```bash
# 实时查看访问日志
tail -f /opt/chongbaoshu-api/logs/access.log

# 查看错误日志（最近50行）
tail -n 50 /opt/chongbaoshu-api/logs/error.log

# 按时间范围搜索
grep "2026-05-24 15:" /opt/chongbaoshu-api/logs/access.log

# 统计今日请求数
grep "$(date +%Y-%m-%d)" /opt/chongbaoshu-api/logs/access.log | wc -l

# 统计今日错误数
grep "$(date +%Y-%m-%d)" /opt/chongbaoshu-api/logs/error.log | wc -l
```

---

## 4. 健康检查

### 4.1 检查端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health-check` | GET | 简单存活检查（秒回） |
| `/api/health-check/deep` | GET | 深度检查（数据库+磁盘+内存） |

### 4.2 简单检查响应

```json
{"code": 0, "message": "ok", "status": "ok", "version": "1.1.0"}
```

### 4.3 深度检查响应

```json
{
    "code": 0,
    "data": {
        "status": "ok",
        "timestamp": "2026-05-24T16:00:00",
        "version": "1.1.0",
        "environment": "production",
        "checks": {
            "database": {
                "status": "ok",
                "latency_ms": 2.35
            },
            "disk": {
                "status": "ok",
                "total_gb": 50.0,
                "free_gb": 30.5,
                "used_percent": 39.0
            },
            "memory": {
                "status": "ok",
                "total_mb": 2048.0,
                "available_mb": 1024.0,
                "used_percent": 50.0
            }
        }
    }
}
```

### 4.4 手动测试

```bash
# 简单检查
curl -s http://localhost:3000/api/health-check | python3 -m json.tool

# 深度检查
curl -s http://localhost:3000/api/health-check/deep | python3 -m json.tool
```

---

## 5. 异常告警

### 5.1 安装健康检查定时器

```bash
# 复制文件
sudo cp deploy/chongbaoshu-api-healthcheck.service /etc/systemd/system/
sudo cp deploy/chongbaoshu-api-healthcheck.timer /etc/systemd/system/

# 加载 & 启用
sudo systemctl daemon-reload
sudo systemctl enable chongbaoshu-api-healthcheck.timer
sudo systemctl start chongbaoshu-api-healthcheck.timer

# 确认状态
sudo systemctl list-timers chongbaoshu-api-healthcheck.timer
```

### 5.2 告警逻辑

```
每 60 秒执行一次 health-check.sh
    │
    ├─ 服务正常 (HTTP 200 + status=ok)
    │   └─ 记录日志，退出
    │
    ├─ 服务降级 (HTTP 200 + status=degraded)
    │   └─ 发送降级告警（含具体组件状态）
    │
    └─ 服务不可用 (超时/非200)
        ├─ 重试 2 次（间隔 3 秒）
        │   ├─ 恢复 → 正常退出
        │   └─ 仍失败 → 自动重启服务
        │       ├─ 重启后恢复 → 发送恢复通知
        │       └─ 重启后仍失败 → 发送严重告警（需人工介入）
        │
```

### 5.3 配置飞书告警

1. 在飞书群中添加「自定义机器人」
2. 复制 Webhook 地址（形如 `https://open.feishu.cn/open-apis/bot/v2/hook/xxx`）
3. 在 `.env` 中配置：
   ```env
   FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
   ```

### 5.4 配置企业微信告警

1. 在企业微信群中添加「群机器人」
2. 复制 Webhook 地址（形如 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx`）
3. 在 `.env` 中配置：
   ```env
   WECOM_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
   ```

### 5.5 手动测试告警

```bash
# 手动执行一次健康检查
sudo -u root /opt/chongbaoshu-api/deploy/health-check.sh

# 查看健康检查日志
tail -f /opt/chongbaoshu-api/logs/health-check.log

# 手动触发测试（临时停止服务来测试告警）
sudo systemctl stop chongbaoshu-api
# 等待约 60 秒，观察告警是否到达
sudo systemctl start chongbaoshu-api
```

---

## 6. 日常运维

### 6.1 版本更新

```bash
cd /opt/chongbaoshu-api

# 拉取最新代码
sudo git pull origin main

# 更新依赖（如有变化）
sudo venv/bin/pip install --no-cache-dir -r requirements.txt

# 执行数据库迁移（如有）
sudo -u www-data venv/bin/python migrate_xxx.py

# 重启服务
sudo systemctl restart chongbaoshu-api

# 确认健康
curl -s http://localhost:3000/api/health-check/deep | python3 -m json.tool
```

### 6.2 数据库备份（SQLite）

```bash
# 添加到 crontab（每天凌晨 3 点）
0 3 * * * www-data cp /opt/chongbaoshu-api/database.sqlite /opt/chongbaoshu-api/backups/db_$(date +\%Y\%m\%d).sqlite

# 保留最近 7 天备份
0 3 * * * www-data find /opt/chongbaoshu-api/backups -name "*.sqlite" -mtime +7 -delete
```

### 6.3 证书续期（如使用 HTTPS）

```bash
# 确保证书自动续期
sudo certbot renew --quiet
sudo systemctl reload nginx  # 或 systemctl reload chongbaoshu-api
```

---

## 7. 故障排查

### 7.1 服务启动失败

```bash
# 查看详细错误
sudo journalctl -u chongbaoshu-api -n 50 --no-pager

# 常见原因：
# 1. 端口被占用 → ss -tlnp | grep 3000
# 2. .env 配置错误 → sudo -u www-data cat /opt/chongbaoshu-api/.env
# 3. 依赖缺失 → sudo venv/bin/pip install -r requirements.txt
# 4. 数据库连接失败 → sudo -u www-data venv/bin/python -c "from config.database import engine; ..."
```

### 7.2 健康检查持续失败

```bash
# 手动检查
curl -v http://localhost:3000/api/health-check

# 检查端口是否在监听
ss -tlnp | grep 3000

# 检查进程是否存在
ps aux | grep uvicorn

# 检查 StartLimit 是否被触发
sudo systemctl show chongbaoshu-api | grep StartLimit
sudo systemctl reset-failed chongbaoshu-api  # 重置限制
```

### 7.3 告警未收到

```bash
# 手动测试 Webhook
curl -X POST "$FEISHU_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d '{"msg_type":"text","content":{"text":"测试告警"}}'

# 检查定时器是否运行
sudo systemctl list-timers --all | grep healthcheck

# 查看定时器日志
sudo journalctl -u chongbaoshu-api-healthcheck.service -n 20
```

### 7.4 日志磁盘占满

```bash
# 查看日志目录大小
du -sh /opt/chongbaoshu-api/logs/

# 紧急清理（保留最近 7 天）
find /opt/chongbaoshu-api/logs/ -name "*.log.*" -mtime +7 -delete

# 检查 logrotate 是否正常运行
sudo cat /var/lib/logrotate/status | grep chongbaoshu
```

---

## 文件清单

```
deploy/
├── chongbaoshu-api.service              # systemd 服务配置
├── chongbaoshu-api.logrotate            # logrotate 日志轮转配置
├── chongbaoshu-api-healthcheck.service  # 健康检查 systemd 服务
├── chongbaoshu-api-healthcheck.timer    # 健康检查定时器（每60秒）
├── health-check.sh                      # 健康检查 + 告警脚本
└── DEPLOY.md                            # 本文档

config/
├── logging_config.py                    # 日志配置模块
└── health.py                            # 深度健康检查模块

logs/                                    # 日志目录（.gitignore）
├── access.log
├── error.log
├── stdout.log
├── stderr.log
└── health-check.log
```
