#!/usr/bin/env bash
# 灰度发布 LangGraph 主循环开关(spec §10.3)
#
# 用法:
#   ./gradual_rollout_langgraph.sh start    # 改为 true
#   ./gradual_rollout_langgraph.sh rollback # 改回 false(紧急回滚)
#   ./gradual_rollout_langgraph.sh status   # 查看当前状态
#
# 注: 本脚本只演示单租户切流。生产 multi-tenant 流量切分走
#      feature flag 服务(LaunchDarkly / 自建)。本脚本用作环境
#      启动引导或单次切流确认。

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"

start() {
    echo "[gradual_rollout] 启用 LangGraph 主循环 (切流)"
    if [ -f "$ENV_FILE" ]; then
        sed -i 's/^LANGGRAPH_ENABLED=.*/LANGGRAPH_ENABLED=true/' "$ENV_FILE"
    fi
    export LANGGRAPH_ENABLED=true
    echo "[gradual_rollout] OK — env: LANGGRAPH_ENABLED=true"
    echo "[gradual_rollout] 灰度 1 周,持续观测 KPI,任何指标越线即 rollback"
}

rollback() {
    echo "[gradual_rollout] EMERGENCY ROLLBACK — 关闭 LangGraph 主循环"
    if [ -f "$ENV_FILE" ]; then
        sed -i 's/^LANGGRAPH_ENABLED=.*/LANGGRAPH_ENABLED=false/' "$ENV_FILE"
    fi
    export LANGGRAPH_ENABLED=false
    echo "[gradual_rollout] OK — env: LANGGRAPH_ENABLED=false"
    echo "[gradual_rollout] react_loop.py 重新接管主循环"
}

status() {
    if [ -f "$ENV_FILE" ] && grep -E "^LANGGRAPH_ENABLED" "$ENV_FILE" >/dev/null; then
        grep -E "^LANGGRAPH_ENABLED" "$ENV_FILE"
    else
        echo "[gradual_rollout] 未设置 LANGGRAPH_ENABLED (默认 false → react_loop)"
    fi
}

case "${1:-status}" in
    start)   start ;;
    rollback) rollback ;;
    status)  status ;;
    *)
        echo "Usage: $0 {start|rollback|status}"
        exit 2
        ;;
esac
