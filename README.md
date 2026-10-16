# 宠宝树后端 API（chongbaoshu-api）

> 犬舍 / 猫舍繁育者 SaaS 的**后端服务**：用宠物档案 + 繁育配种 + 血统谱系 + 免疫提醒，替代繁育者手里的 Excel 与纸本台账。

本仓库是「宠宝树」项目的后端（前端小程序见 [`chongbaoshu-miniapp`](https://github.com/genapohub/chongbaoshu-miniapp)）。

## 这是什么

面向犬舍 / 猫舍繁育者的数据与管理后台。核心能力：

| 模块 | 作用 |
|---|---|
| 宠物档案 | 基础信息、品种、父母、免疫记录 |
| 繁育配种 | 繁育状态机，预产期自动计算 + 近亲检测 |
| 血统谱系 | 递归查询谱系，证书公开验真 |
| 订阅计费 | 三档配额模型，过期自动降级 |
| 免疫提醒 | 按疫苗计划推送续种提醒 |

## 技术栈

| 层 | 选型 |
|---|---|
| 框架 | FastAPI + SQLAlchemy 2.0 |
| 数据库 | 开发 SQLite / 生产 MySQL（Alembic 迁移） |
| 鉴权 | 手机号验证码登录 + JWT |
| 中间件 | 鉴权、审计、限流、上传、错误处理、监控 |
| 测试 | pytest（tests/ 下覆盖 auth / 订阅 / 安全 / 反馈等） |

规模：**18 张表**。

## 本地启动

```bash
pip install -r requirements.txt

# 默认端口 3000，可用环境变量覆盖
PORT=3000 python main.py
# 或：uvicorn main:app --host 127.0.0.1 --port 3000 --reload

# 健康检查
curl http://127.0.0.1:3000/api/health-check
```

```bash
# 测试
pytest tests/
```

## 诚实边界（重要）

- **微信支付商户号未开通。** 订阅为配额模型，配额用尽 / 过期降级逻辑已实现，但无真实收款，未接微信支付。
- **面向微信云托管部署设计。** 含 Dockerfile 与 deploy/ 下的 systemd、nginx、health-check 模板，但实际线上部署未走完。
- 接口与表结构来自本仓库，可现场 `pytest tests/` 复现。

## 目录结构

```text
chongbaoshu-api/
├── main.py             # 应用入口（含健康检查）
├── config/             # 数据库 / 微信 / 日志 / 错误码
├── middleware/         # 鉴权 / 审计 / 限流 / 上传 / 监控
├── migrations/         # Alembic 迁移
├── tests/              # pytest 用例
├── deploy/             # systemd / nginx / 健康检查
└── requirements.txt
```
