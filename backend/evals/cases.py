"""30 条评测用例占位 — 阶段 1 Task 1 完整实现。

骨架先放空 dataclass,便于阶段 1 增量补充。
"""
from dataclasses import dataclass


@dataclass
class EvalCase:
    category: str  # "normal" | "boundary" | "missing" | "induction" | "refusal"
    query: str
    expected_keywords: list[str]  # LLM-as-judge 用关键词


EVAL_CASES: list[EvalCase] = []