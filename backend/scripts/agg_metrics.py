"""汇总 agent 埋点日志,输出 token 基线。

Phase 1 埋了两个事件,合起来是每轮完整 LLM 成本画像:
- agent_turn_metrics —— ReAct 主循环每轮 token(chat_with_tools)
- simple_chat_usage  —— 记忆层 LLM 调用 token(select_relevant / extract /
  consolidate 走的 simple_chat)。Phase 2 要削减的正是这块。

用法:
    # 后端启动时把 stdout 存文件:
    #   uvicorn app.main:app --reload --port 8000 2>&1 | tee -a agent_baseline.log
    python scripts/agg_metrics.py agent_baseline.log

真实使用一阵后跑本脚本,记下数字。Phase 2/3 上线后再跑一遍对比,
即为"少了几次 LLM、省了多少 token"的硬证据。
"""
from __future__ import annotations

import re
import statistics as st
import sys
from collections import defaultdict


def _summarize(path: str) -> None:
    # structlog 默认 ConsoleRenderer 会插入 ANSI 颜色码,先剥离再解析
    ansi = re.compile(r"\x1b\[[0-9;]*m")

    # ReAct 每轮: key=value 扁平字段
    turns: dict[str, list[int]] = defaultdict(list)
    turn_llm_calls: list[int] = []
    # 记忆层: usage={...} dict repr
    simple_calls = 0
    simple_tokens: list[int] = []

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = ansi.sub("", raw)
            if "agent_turn_metrics" in line:
                kv = dict(re.findall(r"(\w+)=(\S+)", line))
                tt = kv.get("total_tokens")
                if tt and tt != "None":
                    turns[kv.get("outcome", "?")].append(int(tt))
                lc = kv.get("llm_calls")
                if lc and lc.isdigit():
                    turn_llm_calls.append(int(lc))
            elif "simple_chat_usage" in line:
                simple_calls += 1
                # usage={'total_tokens': 840, ...} —— 从 dict repr 里抓 total_tokens
                m = re.search(r"'total_tokens':\s*(\d+)", line)
                if m:
                    simple_tokens.append(int(m.group(1)))

    print(f"=== token 基线: {path} ===\n")

    print("[ReAct 主循环 agent_turn_metrics]")
    any_turn = False
    for outcome, vals in sorted(turns.items()):
        if vals:
            any_turn = True
            print(
                f"  {outcome:24s} n={len(vals):3d} "
                f"avg={st.mean(vals):7.0f} median={st.median(vals):7.0f} "
                f"max={max(vals):7d} sum={sum(vals)}"
            )
    if not any_turn:
        print("  (无带 token 的 turn —— provider 是否返回 usage?)")
    if turn_llm_calls:
        print(
            f"  每轮 llm_calls: avg={st.mean(turn_llm_calls):.2f} "
            f"max={max(turn_llm_calls)} (共 {len(turn_llm_calls)} turns)"
        )

    print("\n[记忆层 simple_chat_usage]")
    print(f"  调用次数: {simple_calls}")
    if simple_tokens:
        print(
            f"  token: n={len(simple_tokens)} avg={st.mean(simple_tokens):.0f} "
            f"median={st.median(simple_tokens):.0f} max={max(simple_tokens)} "
            f"sum={sum(simple_tokens)}"
        )
    else:
        print("  (无带 token 记录 —— provider 是否返回 usage?)")

    turn_total = sum(sum(v) for v in turns.values())
    mem_total = sum(simple_tokens)
    print("\n[合计]")
    print(f"  主循环 token 总量: {turn_total}")
    print(f"  记忆层 token 总量: {mem_total}")
    print(f"  全部 token 总量:   {turn_total + mem_total}")


def main() -> None:
    if len(sys.argv) != 2:
        print("用法: python scripts/agg_metrics.py <日志文件>", file=sys.stderr)
        raise SystemExit(2)
    _summarize(sys.argv[1])


if __name__ == "__main__":
    main()
