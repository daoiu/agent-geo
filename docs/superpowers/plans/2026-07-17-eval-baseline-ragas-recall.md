# 评测基准(RAGAS 式三指标 + Recall@5)实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 GEO2 建立检索层(Recall@5 / MRR@5)与回答层(RAGAS 式三指标)两条自动化评测线,并跑出当前系统「改进前」基线。

**Architecture:** 新增 `backend/evals/retrieval/` 模块组。纯函数指标 → 金标集载入 → LLM 半合成金标构建 → RAGAS 式打分 → runner 编排聚合出报告。每层单一职责、可独立单测。首跑即锁定基线,作为后续 ① 混合检索优化的量化对照。

**Tech Stack:** Python 3.11 · pytest(asyncio_mode=auto) · 现有 `EmbeddingService`(bge-small-zh-v1.5) · 现有 `LLMClient`(OpenAI 兼容,`simple_chat`) · 现有 `HybridSearch` · SQLAlchemy async repo。

## Global Constraints

- 语言:所有对话 / docstring / 报告用简体中文。
- 无外网:embedding 走本地 HF 缓存(`settings.models_cache_dir`);LLM 走已配置 provider,无 key 时静默降级不抛错。
- 依赖:**不引入** `ragas` / `pandas` / `datasets` 等重依赖;三指标自研,接口按 ragas 语义命名以便日后替换。
- 测试位置:新测试放 `backend/tests/evals/retrieval/`(pyproject `testpaths=["tests"]`、`pythonpath=["."]`、`asyncio_mode="auto"`),工作目录 `backend/`。
- 降级原则:transient / 无 key → 降级并在报告标注;编程错误(格式错等)照常抛出,不吞。
- 数字诚实:基线数字必须来自真实运行,不硬编码、不编造。

**关键接口(已存在,供各 Task 消费):**
- `app.services.embedding.EmbeddingService.embed(texts: list[str]) -> list[list[float]]`(classmethod,归一化 512 维)
- `app.domain.llm_client.LLMClient(settings)`;`await client.simple_chat(prompt: str) -> str`;`client.available_providers -> list[str]`
- `app.services.hybrid_search.HybridSearch().search(kb_id: str, query: str, top_k: int) -> list[dict]`(每条含 `id` / `content` / `metadata`)
- `app.repositories.knowledge_repo.KnowledgeRepository(session)`:`await list_kbs()`、`await list_chunks(kb_id) -> list[KnowledgeChunkORM]`(ORM 含 `.id/.content/.doc_id/.chunk_index/.kb_id`)
- `app.core.config.get_settings()`;`app.core.db.get_session_factory()`

---

### Task 1: 检索指标纯函数 `retrieval_metrics.py`

**Files:**
- Create: `backend/evals/retrieval/__init__.py`(空文件)
- Create: `backend/evals/retrieval/retrieval_metrics.py`
- Test: `backend/tests/evals/retrieval/test_retrieval_metrics.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float`
  - `mrr_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float`
  - `precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/evals/retrieval/test_retrieval_metrics.py
from evals.retrieval.retrieval_metrics import recall_at_k, mrr_at_k, precision_at_k


def test_recall_full_hit():
    assert recall_at_k(["a", "b", "c"], ["a", "b"], k=3) == 1.0


def test_recall_partial():
    assert recall_at_k(["a", "x", "y"], ["a", "b"], k=3) == 0.5


def test_recall_respects_k():
    # 相关命中排在第 4 位,k=3 截断后召回 0
    assert recall_at_k(["x", "y", "z", "a"], ["a"], k=3) == 0.0


def test_recall_empty_relevant_is_one():
    # 无相关标注时约定返回 1.0(不惩罚)
    assert recall_at_k(["a"], [], k=3) == 1.0


def test_mrr_first_position():
    assert mrr_at_k(["a", "b"], ["a"], k=3) == 1.0


def test_mrr_second_position():
    assert mrr_at_k(["x", "a"], ["a"], k=3) == 0.5


def test_mrr_no_hit():
    assert mrr_at_k(["x", "y"], ["a"], k=3) == 0.0


def test_precision_at_k():
    # 前 3 命中 2 个 → 2/3
    assert round(precision_at_k(["a", "b", "x"], ["a", "b"], k=3), 3) == 0.667


def test_dedup_retrieved():
    # 重复 id 不重复计分
    assert recall_at_k(["a", "a", "b"], ["a", "b"], k=3) == 1.0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_retrieval_metrics.py -v`
Expected: FAIL(ModuleNotFoundError: evals.retrieval.retrieval_metrics)

- [ ] **Step 3: 写最小实现**

```python
# backend/evals/retrieval/retrieval_metrics.py
"""检索评测纯函数:Recall@k / MRR@k / Precision@k。

约定:relevant_ids 为空时 recall 返回 1.0(无标注不惩罚)。
retrieved_ids 会按首次出现去重后再截断到前 k 个。
"""
from __future__ import annotations


def _top_k_unique(retrieved_ids: list[str], k: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for cid in retrieved_ids:
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
        if len(out) >= k:
            break
    return out


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    rel = set(relevant_ids)
    if not rel:
        return 1.0
    top = set(_top_k_unique(retrieved_ids, k))
    return len(top & rel) / len(rel)


def mrr_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    rel = set(relevant_ids)
    if not rel:
        return 1.0
    for rank, cid in enumerate(_top_k_unique(retrieved_ids, k), start=1):
        if cid in rel:
            return 1.0 / rank
    return 0.0


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    rel = set(relevant_ids)
    top = _top_k_unique(retrieved_ids, k)
    if not top:
        return 0.0
    hits = sum(1 for cid in top if cid in rel)
    return hits / len(top)
```

同时创建空文件 `backend/evals/retrieval/__init__.py`。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_retrieval_metrics.py -v`
Expected: PASS(9 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/evals/retrieval/__init__.py backend/evals/retrieval/retrieval_metrics.py backend/tests/evals/retrieval/test_retrieval_metrics.py
git commit -m "feat(eval): 检索指标纯函数 recall/mrr/precision@k + 9 用例"
```

---

### Task 2: 金标集数据结构与载入 `dataset.py`

**Files:**
- Create: `backend/evals/retrieval/dataset.py`
- Test: `backend/tests/evals/retrieval/test_dataset.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `@dataclass GoldenItem`:`id: str`、`kb_id: str`、`query: str`、`relevant_chunk_ids: list[str]`、`reference_answer: str`
  - `load_golden_set(path: str | Path) -> list[GoldenItem]`(逐行 JSON;空行跳过;缺字段抛 `ValueError`)
  - `save_golden_set(items: list[GoldenItem], path: str | Path) -> None`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/evals/retrieval/test_dataset.py
import pytest

from evals.retrieval.dataset import GoldenItem, load_golden_set, save_golden_set


def test_save_then_load_roundtrip(tmp_path):
    items = [
        GoldenItem(id="q1", kb_id="kb1", query="什么是 GEO?",
                   relevant_chunk_ids=["c1", "c2"], reference_answer="GEO 是…"),
    ]
    p = tmp_path / "golden.jsonl"
    save_golden_set(items, p)
    loaded = load_golden_set(p)
    assert loaded == items


def test_load_skips_blank_lines(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"id":"q1","kb_id":"kb1","query":"q","relevant_chunk_ids":["c1"],"reference_answer":"a"}\n\n',
        encoding="utf-8",
    )
    assert len(load_golden_set(p)) == 1


def test_load_missing_field_raises(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"id":"q1","query":"q"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_golden_set(p)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_dataset.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写最小实现**

```python
# backend/evals/retrieval/dataset.py
"""金标数据集:GoldenItem + jsonl 读写。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_REQUIRED = ("id", "kb_id", "query", "relevant_chunk_ids", "reference_answer")


@dataclass
class GoldenItem:
    id: str
    kb_id: str
    query: str
    relevant_chunk_ids: list[str] = field(default_factory=list)
    reference_answer: str = ""


def load_golden_set(path: str | Path) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        missing = [k for k in _REQUIRED if k not in obj]
        if missing:
            raise ValueError(f"金标条目缺字段 {missing}: {line[:80]}")
        items.append(
            GoldenItem(
                id=obj["id"],
                kb_id=obj["kb_id"],
                query=obj["query"],
                relevant_chunk_ids=list(obj["relevant_chunk_ids"]),
                reference_answer=obj["reference_answer"],
            )
        )
    return items


def save_golden_set(items: list[GoldenItem], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_dataset.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/evals/retrieval/dataset.py backend/tests/evals/retrieval/test_dataset.py
git commit -m "feat(eval): 金标集 GoldenItem + jsonl 读写 + 3 用例"
```

---

### Task 3: LLM 半合成金标构建 `dataset_builder.py`

**Files:**
- Create: `backend/evals/retrieval/dataset_builder.py`
- Test: `backend/tests/evals/retrieval/test_dataset_builder.py`

**Interfaces:**
- Consumes: `GoldenItem`(Task 2)、`LLMClient.simple_chat`、`KnowledgeRepository.list_kbs/list_chunks`
- Produces:
  - `async def gen_qa_for_chunk(content: str, llm) -> tuple[str, str]`:调 LLM 产 `(question, reference_answer)`;LLM 返回非法 JSON 时抛 `ValueError`
  - `async def build_golden_set(per_kb: int = 5, llm=None, repo_factory=None) -> list[GoldenItem]`:逐 KB 取前 `per_kb` 个 chunk,生成条目,源 chunk id 作为 `relevant_chunk_ids`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/evals/retrieval/test_dataset_builder.py
import pytest

from evals.retrieval.dataset_builder import gen_qa_for_chunk


class _FakeLLM:
    def __init__(self, reply: str):
        self._reply = reply
    async def simple_chat(self, prompt: str) -> str:
        return self._reply


async def test_gen_qa_parses_json():
    llm = _FakeLLM('{"question": "什么是 GEO?", "answer": "GEO 是生成式引擎优化。"}')
    q, a = await gen_qa_for_chunk("GEO 指生成式引擎优化…", llm)
    assert q == "什么是 GEO?"
    assert "生成式引擎优化" in a


async def test_gen_qa_strips_code_fence():
    llm = _FakeLLM('```json\n{"question": "Q?", "answer": "A"}\n```')
    q, a = await gen_qa_for_chunk("内容", llm)
    assert q == "Q?" and a == "A"


async def test_gen_qa_invalid_json_raises():
    llm = _FakeLLM("这不是 JSON")
    with pytest.raises(ValueError):
        await gen_qa_for_chunk("内容", llm)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_dataset_builder.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写最小实现**

```python
# backend/evals/retrieval/dataset_builder.py
"""LLM 半合成金标构建:从现有 KB chunk 生成 question + 参考答案。

离线一次性脚本,不进热路径。产出交人工抽查后提交 golden_set.jsonl。
"""
from __future__ import annotations

import json
import re

import structlog

from evals.retrieval.dataset import GoldenItem

logger = structlog.get_logger()

_PROMPT = """你是评测数据标注员。基于下面这段知识库文本,提出一个用户最可能问、且答案**完全能由这段文本回答**的中文问题,并给出参考答案。
只输出 JSON,格式:{{"question": "...", "answer": "..."}}

文本:
{content}
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_qa(reply: str) -> tuple[str, str]:
    cleaned = _FENCE_RE.sub("", reply).strip()
    try:
        obj = json.loads(cleaned)
        return str(obj["question"]), str(obj["answer"])
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"LLM 返回无法解析为 QA JSON: {reply[:120]}") from e


async def gen_qa_for_chunk(content: str, llm) -> tuple[str, str]:
    reply = await llm.simple_chat(_PROMPT.format(content=content[:1500]))
    return _parse_qa(reply)


async def build_golden_set(per_kb: int = 5, llm=None, repo_factory=None) -> list[GoldenItem]:
    """逐 KB 取前 per_kb 个 chunk 生成金标条目。

    llm=None → 用默认 LLMClient;repo_factory=None → 用 get_session_factory。
    """
    from app.core.config import get_settings
    from app.core.db import get_session_factory
    from app.domain.llm_client import LLMClient
    from app.repositories.knowledge_repo import KnowledgeRepository

    if llm is None:
        llm = LLMClient(get_settings())
    session_factory = repo_factory or get_session_factory()

    items: list[GoldenItem] = []
    async with session_factory() as session:
        repo = KnowledgeRepository(session)
        kbs = await repo.list_kbs()
        for kb in kbs:
            chunks = await repo.list_chunks(kb.id)
            for i, chunk in enumerate(chunks[:per_kb]):
                try:
                    q, a = await gen_qa_for_chunk(chunk.content, llm)
                except ValueError as e:
                    logger.warning("golden_gen_skip", kb_id=kb.id, chunk_id=chunk.id, error=str(e))
                    continue
                items.append(
                    GoldenItem(
                        id=f"{kb.id[:8]}-{i}",
                        kb_id=kb.id,
                        query=q,
                        relevant_chunk_ids=[chunk.id],
                        reference_answer=a,
                    )
                )
    return items
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_dataset_builder.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/evals/retrieval/dataset_builder.py backend/tests/evals/retrieval/test_dataset_builder.py
git commit -m "feat(eval): LLM 半合成金标构建 + QA 解析 + 3 用例"
```

---

### Task 4: RAGAS 式三指标 `ragas_scorer.py`

**Files:**
- Create: `backend/evals/retrieval/ragas_scorer.py`
- Test: `backend/tests/evals/retrieval/test_ragas_scorer.py`

**Interfaces:**
- Consumes: `LLMClient.simple_chat`、`EmbeddingService.embed`、Task 1 `precision_at_k`
- Produces:
  - `@dataclass RagasScores`:`faithfulness: float`、`answer_relevancy: float`、`context_precision: float`、`llm_available: bool`
  - `context_precision(retrieved_ids, relevant_ids, k) -> float`(纯函数,复用 Task 1 `precision_at_k`)
  - `async def faithfulness(answer, contexts, llm) -> float`
  - `async def answer_relevancy(question, answer, llm, embed_fn) -> float`
  - `async def score(question, answer, contexts, retrieved_ids, relevant_ids, llm, embed_fn=None, k=5) -> RagasScores`(`llm` 无 provider → `llm_available=False`,LLM 类指标记 0.0,`context_precision` 仍算)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/evals/retrieval/test_ragas_scorer.py
from evals.retrieval.ragas_scorer import (
    RagasScores, context_precision, faithfulness, answer_relevancy, score,
)


class _FakeLLM:
    def __init__(self, reply: str, providers=("p",)):
        self._reply = reply
        self.available_providers = list(providers)
    async def simple_chat(self, prompt: str) -> str:
        return self._reply


def _fake_embed(texts):
    # "问题"类文本 → [1,0];其它 → [0,1];用于余弦区分
    return [[1.0, 0.0] if "GEO" in t else [0.0, 1.0] for t in texts]


def test_context_precision_pure():
    assert round(context_precision(["a", "b", "x"], ["a", "b"], k=3), 3) == 0.667


async def test_faithfulness_all_supported():
    llm = _FakeLLM('{"supported": 3, "total": 3}')
    assert await faithfulness("答案", ["ctx"], llm) == 1.0


async def test_faithfulness_partial():
    llm = _FakeLLM('{"supported": 1, "total": 2}')
    assert await faithfulness("答案", ["ctx"], llm) == 0.5


async def test_answer_relevancy_cosine():
    llm = _FakeLLM("关于 GEO 的问题")  # 反推问题
    val = await answer_relevancy("GEO 的问题", "GEO 是…", llm, _fake_embed)
    assert val == 1.0


async def test_score_degrades_without_llm():
    llm = _FakeLLM("x", providers=())  # 无 provider
    s = await score("q", "a", ["ctx"], ["a"], ["a"], llm, _fake_embed, k=3)
    assert s.llm_available is False
    assert s.faithfulness == 0.0 and s.answer_relevancy == 0.0
    assert s.context_precision == 1.0  # 纯函数仍可算
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_ragas_scorer.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写最小实现**

```python
# backend/evals/retrieval/ragas_scorer.py
"""RAGAS 式三指标(自研,离线可跑):faithfulness / answer_relevancy / context_precision。

接口按 ragas 语义命名,日后可无缝替换为官方 ragas 包。
- faithfulness:LLM 判定答案被 context 支撑的句子占比(反幻觉)
- answer_relevancy:LLM 反推问题 → 与原问题 embedding 余弦
- context_precision:纯函数,复用 Recall/Precision 家族(结合金标 relevant_ids)
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from evals.retrieval.retrieval_metrics import precision_at_k

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass
class RagasScores:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    llm_available: bool


def context_precision(retrieved_ids: list[str], relevant_ids: list[str], k: int = 5) -> float:
    return precision_at_k(retrieved_ids, relevant_ids, k)


async def faithfulness(answer: str, contexts: list[str], llm) -> float:
    ctx = "\n".join(contexts)
    prompt = (
        "判断下面【答案】中的每个陈述是否能被【上下文】支撑。"
        '只输出 JSON:{"supported": 支撑句数, "total": 总句数}。\n\n'
        f"【上下文】\n{ctx}\n\n【答案】\n{answer}"
    )
    reply = _FENCE_RE.sub("", await llm.simple_chat(prompt)).strip()
    try:
        obj = json.loads(reply)
        total = int(obj["total"])
        return float(obj["supported"]) / total if total > 0 else 0.0
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def answer_relevancy(question: str, answer: str, llm, embed_fn) -> float:
    prompt = f"根据下面这段答案,反推用户最可能问的一个问题,只输出问题本身:\n{answer}"
    reverse_q = await llm.simple_chat(prompt)
    vecs = embed_fn([question, reverse_q])
    if len(vecs) < 2:
        return 0.0
    return max(0.0, _cosine(vecs[0], vecs[1]))


async def score(
    question: str,
    answer: str,
    contexts: list[str],
    retrieved_ids: list[str],
    relevant_ids: list[str],
    llm,
    embed_fn=None,
    k: int = 5,
) -> RagasScores:
    cp = context_precision(retrieved_ids, relevant_ids, k)
    llm_available = bool(getattr(llm, "available_providers", []))
    if not llm_available:
        return RagasScores(0.0, 0.0, cp, False)
    if embed_fn is None:
        from app.services.embedding import EmbeddingService
        embed_fn = EmbeddingService.embed
    f = await faithfulness(answer, contexts, llm)
    ar = await answer_relevancy(question, answer, llm, embed_fn)
    return RagasScores(f, ar, cp, True)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_ragas_scorer.py -v`
Expected: PASS(6 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/evals/retrieval/ragas_scorer.py backend/tests/evals/retrieval/test_ragas_scorer.py
git commit -m "feat(eval): RAGAS 式三指标(faithfulness/answer_relevancy/context_precision)+ 无 key 降级 + 6 用例"
```

---

### Task 5: 编排与报告 `retrieval_runner.py`

**Files:**
- Create: `backend/evals/retrieval/retrieval_runner.py`
- Test: `backend/tests/evals/retrieval/test_retrieval_runner.py`

**Interfaces:**
- Consumes: `GoldenItem`/`load_golden_set`(T2)、`recall_at_k`/`mrr_at_k`(T1)、`RagasScores`/`score`(T4)、`HybridSearch.search`、`LLMClient`
- Produces:
  - `@dataclass RetrievalReport`:`total, recall_at_5, mrr_at_5, faithfulness, answer_relevancy, context_precision, llm_available, by_kb, details, note`;`to_dict(include_details=False) -> dict`
  - `async def run_baseline(items, search=None, llm=None, embed_fn=None, top_k=5) -> RetrievalReport`
  - `def write_report(report: RetrievalReport, out_dir, date_str) -> Path`(写 `.json` + `.md`)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/evals/retrieval/test_retrieval_runner.py
from evals.retrieval.dataset import GoldenItem
from evals.retrieval.retrieval_runner import RetrievalReport, run_baseline, write_report


class _FakeSearch:
    async def search(self, kb_id, query, top_k):
        # 第一条命中金标 c1;第二条全 miss
        if "命中" in query:
            return [{"id": "c1", "content": "相关内容"}, {"id": "z", "content": "x"}]
        return [{"id": "z", "content": "x"}]


class _FakeLLM:
    available_providers = []  # 触发降级,runner 不需要真 LLM
    async def simple_chat(self, prompt): return ""


def _fake_embed(texts): return [[1.0, 0.0] for _ in texts]


async def test_run_baseline_aggregates():
    items = [
        GoldenItem(id="q1", kb_id="kb1", query="命中问题", relevant_chunk_ids=["c1"], reference_answer="a"),
        GoldenItem(id="q2", kb_id="kb1", query="未命中问题", relevant_chunk_ids=["c1"], reference_answer="a"),
    ]
    rep = await run_baseline(items, search=_FakeSearch(), llm=_FakeLLM(), embed_fn=_fake_embed, top_k=5)
    assert rep.total == 2
    assert rep.recall_at_5 == 0.5      # 一条命中一条 miss
    assert rep.llm_available is False
    assert "kb1" in rep.by_kb


async def test_write_report_creates_files(tmp_path):
    rep = RetrievalReport(
        total=1, recall_at_5=0.5, mrr_at_5=0.5, faithfulness=0.0,
        answer_relevancy=0.0, context_precision=1.0, llm_available=False,
        by_kb={}, details=[], note="test",
    )
    md = write_report(rep, tmp_path, "2026-07-17")
    assert md.exists()
    assert (tmp_path / "retrieval-baseline-2026-07-17.json").exists()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_retrieval_runner.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 写最小实现**

```python
# backend/evals/retrieval/retrieval_runner.py
"""编排:载入金标 → 跑 HybridSearch → Recall/MRR → 生成答案 → RAGAS → 聚合报告。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from evals.retrieval.dataset import GoldenItem
from evals.retrieval.ragas_scorer import score
from evals.retrieval.retrieval_metrics import mrr_at_k, recall_at_k

logger = structlog.get_logger()


@dataclass
class RetrievalReport:
    total: int
    recall_at_5: float
    mrr_at_5: float
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    llm_available: bool
    by_kb: dict = field(default_factory=dict)
    details: list = field(default_factory=list)
    note: str = ""

    def to_dict(self, include_details: bool = False) -> dict:
        d = {
            "total": self.total,
            "recall_at_5": round(self.recall_at_5, 3),
            "mrr_at_5": round(self.mrr_at_5, 3),
            "faithfulness": round(self.faithfulness, 3),
            "answer_relevancy": round(self.answer_relevancy, 3),
            "context_precision": round(self.context_precision, 3),
            "llm_available": self.llm_available,
            "by_kb": self.by_kb,
            "note": self.note,
        }
        if include_details:
            d["details"] = self.details
        return d


async def _generate_answer(query: str, contexts: list[str], llm) -> str:
    if not getattr(llm, "available_providers", []):
        return ""
    ctx = "\n".join(contexts[:5])
    prompt = f"仅根据下面资料回答问题,不要编造。\n资料:\n{ctx}\n\n问题:{query}"
    return await llm.simple_chat(prompt)


async def run_baseline(items, search=None, llm=None, embed_fn=None, top_k: int = 5) -> RetrievalReport:
    if search is None:
        from app.services.hybrid_search import HybridSearch
        search = HybridSearch()
    if llm is None:
        from app.core.config import get_settings
        from app.domain.llm_client import LLMClient
        llm = LLMClient(get_settings())

    details: list[dict] = []
    for it in items:
        hits = await search.search(kb_id=it.kb_id, query=it.query, top_k=top_k)
        retrieved_ids = [h["id"] for h in hits]
        contexts = [h.get("content", "") for h in hits]
        recall = recall_at_k(retrieved_ids, it.relevant_chunk_ids, top_k)
        mrr = mrr_at_k(retrieved_ids, it.relevant_chunk_ids, top_k)
        answer = await _generate_answer(it.query, contexts, llm)
        rag = await score(
            it.query, answer, contexts, retrieved_ids, it.relevant_chunk_ids,
            llm, embed_fn, k=top_k,
        )
        details.append({
            "id": it.id, "kb_id": it.kb_id, "query": it.query,
            "recall": recall, "mrr": mrr,
            "faithfulness": rag.faithfulness,
            "answer_relevancy": rag.answer_relevancy,
            "context_precision": rag.context_precision,
        })

    n = len(details) or 1
    def _avg(key: str) -> float:
        return sum(d[key] for d in details) / n

    by_kb: dict[str, dict] = {}
    for d in details:
        b = by_kb.setdefault(d["kb_id"], {"count": 0, "recall": 0.0})
        b["count"] += 1
        b["recall"] += d["recall"]
    for kb_id, b in by_kb.items():
        b["recall"] = round(b["recall"] / b["count"], 3)

    llm_available = any(d["faithfulness"] or d["answer_relevancy"] for d in details) or \
        bool(getattr(llm, "available_providers", []))

    return RetrievalReport(
        total=len(details),
        recall_at_5=_avg("recall"),
        mrr_at_5=_avg("mrr"),
        faithfulness=_avg("faithfulness"),
        answer_relevancy=_avg("answer_relevancy"),
        context_precision=_avg("context_precision"),
        llm_available=bool(getattr(llm, "available_providers", [])),
        by_kb=by_kb,
        details=details,
        note="检索基线;LLM 指标在无 key 时为 0",
    )


def write_report(report: RetrievalReport, out_dir, date_str: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"retrieval-baseline-{date_str}.json").write_text(
        json.dumps(report.to_dict(include_details=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = out / f"retrieval-baseline-{date_str}.md"
    d = report.to_dict()
    md.write_text(
        f"""# 检索评测基线 {date_str}

| 指标 | 值 |
|---|---|
| 样本数 | {d['total']} |
| Recall@5 | {d['recall_at_5']} |
| MRR@5 | {d['mrr_at_5']} |
| faithfulness | {d['faithfulness']} |
| answer_relevancy | {d['answer_relevancy']} |
| context_precision | {d['context_precision']} |
| LLM 指标可用 | {d['llm_available']} |

> {d['note']}
""",
        encoding="utf-8",
    )
    return md
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/evals/retrieval/test_retrieval_runner.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd backend && python -m pytest tests/evals/retrieval/ -v
git add backend/evals/retrieval/retrieval_runner.py backend/tests/evals/retrieval/test_retrieval_runner.py
git commit -m "feat(eval): retrieval_runner 编排聚合 + 报告输出 + 2 用例"
```

---

### Task 6: 构建金标集 + 跑首个基线(真实运行 + 人工抽查)

> 本 Task 有真实 LLM/embedding 调用与人工环节,非纯 TDD。产出提交入库。

**Files:**
- Create: `backend/evals/retrieval/golden_set.jsonl`(生成 + 人工抽查后)
- Create: `backend/scripts/build_golden_set.py`(一次性入口)
- Create: `reports/eval/retrieval-baseline-2026-07-17.{md,json}`

- [ ] **Step 1: 写生成脚本**

```python
# backend/scripts/build_golden_set.py
"""一次性:生成金标集草稿到 evals/retrieval/golden_set.draft.jsonl。人工抽查后改名为 golden_set.jsonl。"""
import asyncio
from pathlib import Path

from evals.retrieval.dataset import save_golden_set
from evals.retrieval.dataset_builder import build_golden_set


async def main():
    items = await build_golden_set(per_kb=5)
    out = Path("evals/retrieval/golden_set.draft.jsonl")
    save_golden_set(items, out)
    print(f"生成 {len(items)} 条草稿 → {out}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 运行生成草稿**

Run: `cd backend && python -m scripts.build_golden_set`
Expected: 打印「生成 N 条草稿」(N 约 40-50),生成 `evals/retrieval/golden_set.draft.jsonl`

- [ ] **Step 3: 人工抽查**

打开 `golden_set.draft.jsonl`,抽查约 10 条:question 是否自然、reference_answer 是否确实由该 chunk 支撑、relevant_chunk_ids 是否正确。删掉明显不合格的条目,修正后另存为 `evals/retrieval/golden_set.jsonl`。

- [ ] **Step 4: 跑首个基线**

```python
# 临时脚本 backend/scripts/run_baseline.py
import asyncio
from pathlib import Path
from evals.retrieval.dataset import load_golden_set
from evals.retrieval.retrieval_runner import run_baseline, write_report

async def main():
    items = load_golden_set("evals/retrieval/golden_set.jsonl")
    rep = await run_baseline(items)
    md = write_report(rep, Path("../reports/eval"), "2026-07-17")
    print(rep.to_dict())
    print("报告:", md)

if __name__ == "__main__":
    asyncio.run(main())
```

Run: `cd backend && python -m scripts.run_baseline`
Expected: 打印指标 dict,生成 `reports/eval/retrieval-baseline-2026-07-17.{md,json}`。记下 Recall@5 的真实值 —— 这是简历「改进前」数字的出处。

- [ ] **Step 5: 提交**

```bash
git add backend/evals/retrieval/golden_set.jsonl backend/scripts/build_golden_set.py backend/scripts/run_baseline.py reports/eval/retrieval-baseline-2026-07-17.md reports/eval/retrieval-baseline-2026-07-17.json
git commit -m "chore(eval): 金标集(人工抽查)+ 检索基线首跑报告"
```

---

### Task 7: 更新简历/README 为真实基线描述

**Files:**
- Modify: `docs/RESUME_AI_Agent_Target.md`(RAG 段落追加评测能力)
- Modify: `README.md`(评测章节补充检索基线)

- [ ] **Step 1: 用真实数字改写**

将 Task 6 得到的真实 Recall@5 基线值填入。措辞示例(把 `<X>` 换成真实值):

```markdown
- **RAG 评测闭环**:自建检索金标集(~50 条,LLM 半合成 + 人工抽查),
  RAGAS 式三指标(faithfulness / answer_relevancy / context_precision)+ Recall@5 / MRR@5 自动化评测;
  当前基线 Recall@5 = <X>(混合检索优化前),作为后续 Cross-Encoder 重排 / 查询改写 / 语义缓存的量化对照。
```

- [ ] **Step 2: 提交**

```bash
git add docs/RESUME_AI_Agent_Target.md README.md
git commit -m "docs: 评测闭环真实基线数字入简历/README"
```

---

## Self-Review

**Spec coverage:**
- 架构/模块表 → Task 1-5 逐一实现 ✅
- 三指标定义 → Task 4 ✅
- 数据流(金标→检索→指标→答案→RAGAS→报告)→ Task 5 + Task 6 ✅
- 规模~50 + 首跑基线 → Task 6 ✅
- 错误处理(无 key 降级 / 纯函数仍可算 / 格式错抛出)→ Task 1(空 relevant)/ Task 2(缺字段抛)/ Task 4(降级)/ Task 5 ✅
- 测试(metrics/scorer/runner/builder)→ Task 1-5 均含 ✅
- 交付物(模块/金标/报告/文档)→ Task 6-7 ✅
- 非目标(Cross-Encoder/Plan-Execute/Redis/官方 ragas)→ 未纳入任务 ✅

**Placeholder scan:** 无 TBD;每个代码步骤含完整代码;Task 7 措辞含 `<X>` 是**有意**留给真实运行数字,非占位缺陷。

**Type consistency:** `GoldenItem`/`RagasScores`/`RetrievalReport` 字段在 T2/T4/T5 定义并在 T5/T6 一致引用;`recall_at_k`/`mrr_at_k`/`precision_at_k` 签名 T1 定义,T4/T5 一致调用;`score(...)` 参数顺序在 T4 定义、T5 调用一致 ✅
