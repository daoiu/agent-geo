# LangGraph 双跑 evals — 收尾 handoff (2026-07-14)

> Plan task 16 — evals/runner.py --compare 量化收尾

## Stub-mode 双跑结果(本地)

跑 `compare_evals` with 2 paths 使用同样的 stub SSE chunk returns:

```
{
  "overall_match": 1.0,
  "tool_call_match": 1.0,
  "handoff_match": 1.0,
  "sse_event_count_equal": true
}
```

✅ 全部指标 ≥ 0.95,tool_call 与 handoff_match = 1.0,SSE_event_count_equal.

注:这是 stub-mode 跑通,确认 `compare_evals` 逻辑 + report 输出无误。**生产化指标需要在 `langgraph_enabled = True` 真实环境下跑 ≥ 5 天,记录到本次灰度 KPI 表**(见 Task 17)。

## 跑命令

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/test_evals_compare_runner.py -v    # 4/4 unit
.venv/Scripts/python.exe -m evals.runner --compare                          # 产 diff_report.md
```

## 灰度 1 周 KPI(尚需生产化观测)

| 指标 | 阈值 | 失败动作 |
|---|---|---|
| overall_text_match (ROUGE-L) | ≥ 0.95 | revert flag |
| tool_call_match | = 1.0 (100%) | revert flag |
| handoff_event_match | = 1.0 (100%) | revert flag |
| SSE_event_count_equal | true | revert flag |
| P95 turn latency | ≤ react_loop + 10% | revert flag |
| tool_call 成功率 | ≥ 99% | revert flag |
| Sentry 异常率 | ≤ react_loop 同期 | revert flag |

## 输出文件位置

```
backend/reports/eval/diff/<date>.md     # 每次 compare 出的 markdown diff 报告
backend/reports/eval/baseline.txt      # react_loop baseline
```

## 下一步

- Task 17 灰度切流:`.env.example` 加 `LANGGRAPH_ENABLED=false`,Settings 默认 False,1 个里程碑后改 True
- 最终 review 派 code-reviewer 全分支扫描
