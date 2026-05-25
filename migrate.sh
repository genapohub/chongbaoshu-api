#!/usr/bin/env bash
# migrate.sh — 宠宝树 API 数据库迁移便捷脚本
# 用法：
#   ./migrate.sh upgrade          # 升级到最新版本（日常部署用）
#   ./migrate.sh status           # 查看当前版本和未执行差异
#   ./migrate.sh new "描述"       # 自动生成新迁移（autogenerate）
#   ./migrate.sh new_empty "描述" # 生成空白迁移（手写 upgrade/downgrade）
#   ./migrate.sh downgrade -1     # 回退一步
#   ./migrate.sh history          # 查看历史记录

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 优先用 venv 里的 alembic，否则回退到 PATH / 用户安装路径
if command -v alembic &>/dev/null; then
    ALEMBIC="alembic"
elif [ -f "$HOME/Library/Python/3.9/bin/alembic" ]; then
    ALEMBIC="$HOME/Library/Python/3.9/bin/alembic"
else
    echo "❌ 找不到 alembic，请先执行：pip install alembic==1.13.1"
    exit 1
fi

CMD="${1:-upgrade}"
shift || true

case "$CMD" in
    upgrade)
        echo "▶ 升级数据库到最新版本..."
        $ALEMBIC upgrade head
        echo "✅ 数据库已是最新版本"
        ;;
    status)
        echo "▶ 当前版本："
        $ALEMBIC current
        echo ""
        echo "▶ Schema 差异检查："
        $ALEMBIC check && echo "✅ 无待迁移变更" || true
        ;;
    new)
        MSG="${1:-auto_migration}"
        echo "▶ 自动生成迁移：$MSG"
        $ALEMBIC revision --autogenerate --message "$MSG"
        echo "✅ 迁移文件已生成，请在 migrations/versions/ 中检查后执行 upgrade"
        ;;
    new_empty)
        MSG="${1:-manual_migration}"
        echo "▶ 生成空白迁移：$MSG"
        $ALEMBIC revision --message "$MSG"
        echo "✅ 空白迁移文件已生成，请手写 upgrade/downgrade 后执行 upgrade"
        ;;
    downgrade)
        STEP="${1:--1}"
        echo "▶ 回退 $STEP 步..."
        $ALEMBIC downgrade "$STEP"
        echo "✅ 回退完成"
        ;;
    history)
        $ALEMBIC history --verbose
        ;;
    *)
        echo "用法：$0 {upgrade|status|new '描述'|new_empty '描述'|downgrade [-1]|history}"
        exit 1
        ;;
esac
