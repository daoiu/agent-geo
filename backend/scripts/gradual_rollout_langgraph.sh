#!/usr/bin/env bash
# 灰度发布 LangGraph 主循环开关(spec §10.3)
#
# 2026-07-17 CR-4:本脚本已废弃。LANGGRAPH_ENABLED 字段已删除(2026-07-17
# plan Task 8),LangGraph 是唯一 agent 执行路径,react_loop.py 驱动已删除
# (plan Task 10)。无法再回滚到 react_loop 路径。
#
# 当前唯一灰度维度是 AGENT_ORCHESTRATOR_ENABLED(②b 编排层),没有等价的
# 灰度脚本;如需 ②b 灰度,请直接在 .env 改 AGENT_ORCHESTRATOR_ENABLED。
#
# 本脚本保留仅为运维提示旧入口;执行 start/rollback/status 都会 no-op +
# 提示用户看新版说明。
#
# 旧用法(2026-07-17 前):
#   ./gradual_rollout_langgraph.sh start    # 改为 true
#   ./gradual_rollout_langgraph.sh rollback # 改回 false(紧急回滚)
#   ./gradual_rollout_langgraph.sh status   # 查看当前状态

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"

note() {
    cat <<EOF
[gradual_rollout_langgraph] 本脚本已废弃(2026-07-17)。

LangGraph 是唯一 agent 执行路径(react_loop.py 已删除)。无 LANGGRAPH_ENABLED
灰度维度 — LangGraph 默认就是开启的。

灰度维度现仅剩:
- AGENT_ORCHESTRATOR_ENABLED  (默认 false → LangGraph;true → ②b 编排层)

如需禁用 ②b 编排层,直接改 .env:
    AGENT_ORCHESTRATOR_ENABLED=false
EOF
}

start() {
    note
}

rollback() {
    note
}

status() {
    note
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
