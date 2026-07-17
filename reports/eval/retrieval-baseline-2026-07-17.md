# 检索评测基线 2026-07-17

| 指标 | 值 |
|---|---|
| 样本数 | 4 |
| Recall@5 | 1.0 |
| MRR@5 | 0.833 |
| faithfulness | 0.0 |
| answer_relevancy | 0.709 |
| context_precision | 0.25 |
| LLM 指标可用 | True |

> 环境标注:真混合检索已生效(HybridSearch 不再 fallback);金标集仅 4 条(1 个 KB / 4 chunks),每条 query 只标注 1 个 relevant chunk,Recall@5=1.0 受 top_k 完全覆盖影响,context_precision@5=0.25 反映真实精确率(其他 3 个 chunks 不是该 query 的目标)。
