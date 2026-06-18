# Gitee 流水线配置说明

## 首次启用步骤

### 1. 配置流水线变量
进入 Gitee 仓库 → 设置 → 流水线变量，添加以下变量：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `SSH_HOST` | `你的服务器IP` | 生产服务器地址 |
| `SSH_USER` | `root` | SSH 用户名 |
| `SSH_KEY` | `Base64编码的私钥` | `cat ~/.ssh/id_rsa \| base64` |

### 2. 服务器准备
在服务器上执行一次初始化：
```bash
cd /opt/chongbaoshu-api
chmod +x deploy/setup_production.sh
./deploy/setup_production.sh
```

### 3. 启用流水线
Gitee 仓库 → 流水线 → 启用

## 开发→生产同步流程

```
本地开发 (dev/feature 分支)
  ↓ git push
Gitee (dev 分支)
  ↓ Pull Request / Merge
Gitee (master 分支)
  ↓ 自动触发
流水线（测试 → 部署）
  ↓
生产服务器
```

### 日常开发流程

1. 在本地创建功能分支开发
2. 推送到 Gitee 对应分支
3. 在 Gitee 创建 Pull Request 合并到 master
4. 合并后流水线自动：跑测试 → 部署到生产

### 数据库变更

- 开发环境：直接修改 models，Alembic 自动生成迁移
- 生产环境：`alembic upgrade head` 在部署脚本中自动执行
- **注意**：涉及数据迁移的变更需先在 staging 验证

### 回滚

```bash
# SSH 到服务器
ssh root@<服务器IP>

# 回滚代码
cd /opt/chongbaoshu-api
git log --oneline -5          # 找到上一个稳定版本
git reset --hard <commit-hash>

# 回滚数据库（必要时）
cd /opt/chongbaoshu-api
source .venv/bin/activate
python -m alembic downgrade -1

# 重启
systemctl restart chongbaoshu-api
```
