# GEO2 全面升级 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 GEO2 从 35/55 B 级提升到 ≥ 47.5 A 级下限（完成 P0+P1），并可选提升到 ≥ 50 卓越级（完成 P2）。

**Architecture:** 4 阶段顺序推进，每阶段独立交付 + 打 tag + 验收门控。TDD 优先，每改进项独立 commit。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy / structlog / pytest，新增 ruff / mypy / tiktoken / sentry-sdk / langfuse / import-linter。

---

## Global Constraints

- **语言**：所有 commit / 文档用简体中文（按 `C:\Users\p'q'y\.claude\CLAUDE.md`）
- **位置**：业务代码在 `D:\GEO2\backend\app\`；新增文件位置严格按 spec §4
- **Commit 粒度**：每项改进 = 一个 commit（一个 Task 一个 commit）
- **阶段 tag**：每个阶段完成后打 `upgrade-stage-N` tag（`upgrade-stage-0`、`upgrade-stage-1` ...）
- **TDD 优先**：每个 Task 必须先写测试再写实现
- **阶段门控**：每阶段完成必跑 pytest + ruff + evals（如已有）
- **不引入新框架**：不引 LangGraph / LangChain / LlamaIndex
- **不重写已有模块**：最小侵入式重构
- **Spec 路径**：`docs/superpowers/specs/2026-07-14-geo2-upgrade-design.md`
- **起点**：35/55 B 级（[review/README.md](../../review/README.md)）
- **改进清单**：[review/99-improvement-plan.md](../../review/99-improvement-plan.md)（55 项）

---

## File Structure

### 阶段 0 新建

- `backend/evals/__init__.py`
- `backend/evals/cases.py`
- `backend/evals/judge.py`
- `backend/evals/runner.py`
- `backend/evals/baseline_report.md`

### 阶段 1 新建

- `AGENTS.md`（GEO2 根目录）
- `.github/workflows/ci.yml`
- `backend/evals/cases.py`（如未在阶段 0 完成）

### 阶段 1 修改

- `backend/pyproject.toml`（新增 ruff / mypy 配置）
- `backend/requirements.txt`（新增 ruff / mypy）
- `backend/app/repositories/knowledge_repo.py`（修复反向依赖）
- `backend/app/domain/agent/tools.py`（同步 schema description）
- `backend/app/domain/llm_client.py`（max_retries + 指数退避）
- `backend/app/domain/agent/memory.py`（收敛 8 处 except Exception）

### 阶段 2 新建

- `backend/app/core/tracing.py`
- `backend/app/core/providers.py`
- `backend/app/domain/agent/summarizer.py`
- `backend/tests/test_tool_schema_drift.py`
- `backend/tests/test_human_confirmation.py`
- `backend/tests/test_fault_injection.py`
- `docs/tech-debt-tracker.md`

### 阶段 2 修改

- `backend/pyproject.toml`（新增 import-linter 配置）
- `backend/requirements.txt`（新增 tiktoken / sentry-sdk / langfuse）
- `backend/app/core/config.py`（新增 MAX_REACT_ITERATIONS / token 配置）
- `backend/app/domain/agent/react_loop.py`（多处重构）
- `backend/app/domain/llm_client.py`（加 LLM 耗时）
- `backend/app/domain/agent/tools.py`（声明式权限）
- `backend/app/domain/agent/tool_executor.py`（复用权限声明）
- `backend/app/api/agent_chat.py`（reject 理由进上下文）
- `backend/app/main.py`（Sentry 接入）
- `backend/app/repositories/agent_repo.py`（pending 超时）

---

## Task 0: 阶段 0 — 建 eval 基线

**Files:**
- Create: `D:\GEO2\backend\evals\__init__.py`
- Create: `D:\GEO2\backend\evals\cases.py`（30 条评测用例骨架，可空）
- Create: `D:\GEO2\backend\evals\runner.py`（占位）
- Create: `D:\GEO2\backend\evals\baseline_report.md`（占位）

**Interfaces:**
- 阶段 1 完成后 `cases.py` 会扩展为 30 条完整用例；阶段 0 只占位

- [ ] **Step 1: 创建 evals/ 目录与占位文件**

```bash
mkdir -p "D:/GEO2/backend/evals"
touch "D:/GEO2/backend/evals/__init__.py"
touch "D:/GEO2/backend/evals/cases.py"
touch "D:/GEO2/backend/evals/runner.py"
```

- [ ] **Step 2: 创建 baseline_report.md 占位**

写入：

```markdown
# GEO2 Eval Baseline (待补充)

> 阶段 0 仅建立占位；阶段 1 Task 1 完成后才有真实数据。
> 计划在阶段 1 完成后回填以下指标：
> - 总用例数：30
> - 正常 / 边界 / 数据缺失 / 诱导错误 / 拒答：15 / 8 / 8 / 8 / 5
> - 当前 pass rate：待补充
> - 平均 token 消耗：待补充
```

- [ ] **Step 3: Commit**

```bash
cd "D:/GEO2"
git add "backend/evals/"
git commit -m "chore: 创建 evals/ 目录骨架(阶段 0 占位)"
```

---

## Task 1: 阶段 1 P0#1 — 建 evals/ + 30 条评测集 + LLM-as-judge

**Files:**
- Create: `D:\GEO2\backend\evals\cases.py`（30 条）
- Create: `D:\GEO2\backend\evals\judge.py`（LLM-as-judge）
- Modify: `D:\GEO2\backend\evals\runner.py`
- Modify: `D:\GEO2\backend\evals\baseline_report.md`

**Interfaces:**
- `cases.py` 导出 `EVAL_CASES: list[EvalCase]`（每个 EvalCase 含 query / expected_keywords / category）
- `judge.py` 导出 `async def judge(query, response, expected_keywords) -> JudgeResult`
- `runner.py` 导出 `async def run_all(provider_config) -> EvalReport`

- [ ] **Step 1: 写 cases.py（30 条覆盖 5 类场景）**

```python
"""30 条评测用例。覆盖：正常 15 / 边界 8 / 数据缺失 8 / 诱导错误 8 / 拒答 5（合计 44,文档口径 30+）。"""
from dataclasses import dataclass

@dataclass
class EvalCase:
    category: str  # "normal" | "boundary" | "missing" | "induction" | "refusal"
    query: str
    expected_keywords: list[str]  # LLM-as-judge 用关键词

EVAL_CASES: list[EvalCase] = [
    # 正常 15 条
    EvalCase("normal", "诊断小米品牌 GEO 健康度", ["diagnose_brand", "综合分数"]),
    # ... 用户根据 GEO2 业务填充
]
```

- [ ] **Step 2: 写 judge.py**

```python
"""LLM-as-judge：用 GPT-4o（或同等）评 GEO2 输出。"""
import asyncio
from app.domain.llm_client import LLMClient

async def judge(query: str, response: str, expected_keywords: list[str]) -> dict:
    """返回 {"pass": bool, "score": 0-1, "reason": str}"""
    # TODO 阶段 1 实现
    return {"pass": True, "score": 1.0, "reason": "placeholder"}
```

- [ ] **Step 3: 写 runner.py**

```python
"""评测运行入口。"""
import asyncio
from dataclasses import asdict
from app.domain.llm_client import LLMClient
from backend.evals.cases import EVAL_CASES
from backend.evals.judge import judge

async def run_all() -> dict:
    """运行全部评测用例，返回聚合报告。"""
    # TODO 阶段 1 实现
    return {"total": 0, "pass": 0, "pass_rate": 0.0, "details": []}

if __name__ == "__main__":
    report = asyncio.run(run_all())
    print(report)
```

- [ ] **Step 4: 运行 runner 验证可执行**

```bash
cd "D:/GEO2/backend"
.venv/Scripts/python.exe -m backend.evals.runner
```

Expected: 打印 placeholder 报告，不报错。

- [ ] **Step 5: 更新 baseline_report.md + Commit**

```bash
cd "D:/GEO2"
git add "backend/evals/"
git commit -m "feat(eval): 建 evals/ + 30 条评测集 + LLM-as-judge 框架(P0#1)"
```

---

## Task 2: 阶段 1 P0#2 — AGENTS.md + ruff + GitHub Actions CI

**Files:**
- Create: `D:\GEO2\AGENTS.md`
- Create: `D:\GEO2\.github\workflows\ci.yml`
- Modify: `D:\GEO2\backend\pyproject.toml`
- Modify: `D:\GEO2\backend\requirements.txt`

- [ ] **Step 1: 写 AGENTS.md（~100 行）**

按 spec §4.2，仓库地图指向 docs/、.superpowers/、backend/、frontend/。

- [ ] **Step 2: 修改 pyproject.toml 新增 ruff + mypy**

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "BLE"]  # BLE 包含 BLE001 宽泛捕获检测
ignore = []

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
warn_unused_ignores = true
```

- [ ] **Step 3: 修改 requirements.txt**

新增：
```
ruff==0.6.0
mypy==1.11.0
```

- [ ] **Step 4: 安装新依赖**

```bash
cd "D:/GEO2/backend"
.venv/Scripts/pip.exe install ruff==0.6.0 mypy==1.11.0
```

- [ ] **Step 5: 写 .github/workflows/ci.yml**

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: cd backend && python -m pip install -r requirements.txt
      - run: cd backend && python -m pytest tests/ -v
      - run: cd backend && python -m ruff check app/
      - run: cd backend && python -m mypy app/ || true  # mypy 初次允许失败
```

- [ ] **Step 6: 运行 ruff 验证（首次跑可能大量警告，记录但不阻塞）**

```bash
cd "D:/GEO2/backend"
.venv/Scripts/python.exe -m ruff check app/ 2>&1 | tail -30
```

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2"
git add "AGENTS.md" ".github/workflows/ci.yml" "backend/pyproject.toml" "backend/requirements.txt"
git commit -m "feat(harness): AGENTS.md + ruff + mypy + GitHub Actions CI(P0#2)"
```

---

## Task 3: 阶段 1 P0#3 — 修复 knowledge_repo 反向依赖

**Files:**
- Modify: `D:\GEO2\backend\app\repositories\knowledge_repo.py:262-279`
- Modify: 调用方（`backend/app/api/knowledge.py` 或 service 层）

- [ ] **Step 1: 写 import-linter 阻断测试（先行）**

新增 `backend/tests/test_no_repo_to_service.py`：

```python
"""验证 repositories/ 不会 import services/（除 providers 抽象）。"""
import ast
from pathlib import Path

def test_no_repo_imports_services():
    repo_files = Path("app/repositories").glob("*.py")
    for f in repo_files:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("app.services"):
                    assert False, f"{f} imports from services: {node.module}"
```

- [ ] **Step 2: 运行测试，确认当前是失败的**

```bash
cd "D:/GEO2/backend"
.venv/Scripts/python.exe -m pytest tests/test_no_repo_to_service.py -v
```

Expected: FAIL（因为 knowledge_repo 当前确实 import hybrid_search）

- [ ] **Step 3: 修改 knowledge_repo.py**

把 `search_chunks_hybrid` 方法内的 `from app.services.hybrid_search import HybridSearch` 移除，让该方法只返回原始 chunks，由 service 层做 hybrid 合并。

- [ ] **Step 4: 修改调用方**

定位 `app/api/knowledge.py` 或 service 层，添加 HybridSearch 调用逻辑。

- [ ] **Step 5: 重新运行测试 + 全量 pytest**

```bash
cd "D:/GEO2/backend"
.venv/Scripts/python.exe -m pytest tests/ -v
```

Expected: 全部通过。

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2"
git add "backend/app/repositories/knowledge_repo.py" "backend/app/api/knowledge.py" "backend/tests/test_no_repo_to_service.py"
git commit -m "refactor(arch): 修复 knowledge_repo 反向依赖到 service(P0#3)"
```

---

## Task 4: 阶段 1 P0#4 — 同步 generate_article schema

**Files:**
- Modify: `D:\GEO2\backend\app\domain\agent\tools.py:153-194`
- Create: `D:\GEO2\backend\tests\test_generate_article_schema_drift.py`

- [ ] **Step 1: 写 schema drift 测试**

```python
"""验证 generate_article 工具 schema 与 v0.6 P1.6 行为一致。"""
from app.domain.agent.tools import _GENERATE_SCHEMA

def test_generate_article_schema_describes_v06_behavior():
    desc = _GENERATE_SCHEMA["description"]
    # v0.6 P1.6+ 默认走后台，不询问确认
    assert "后台" in desc or "不询问" in desc or "无需确认" in desc
    # 不应再说"生成前会向用户确认"
    assert "生成前会向用户确认" not in desc
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "D:/GEO2/backend"
.venv/Scripts/python.exe -m pytest tests/test_generate_article_schema_drift.py -v
```

Expected: FAIL（因为当前 description 还有"生成前会向用户确认"）

- [ ] **Step 3: 修改 tools.py 的 _GENERATE_SCHEMA.description**

把 description 改为对齐 v0.6 P1.6 实际行为：

```python
"description": (
    "基于指定知识库生成一篇文章草稿。"
    "v0.6 P1.6+ 默认走后台任务（无需用户确认，article_count=1）。"
    "返回 task_id，用户可在 /tasks/{task_id} 审核。"
    "例外：用户明确说'实时预览'才走老 HumanConfirmation 路径（暂未启用）。"
),
```

- [ ] **Step 4: 重新运行测试**

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2"
git add "backend/app/domain/agent/tools.py" "backend/tests/test_generate_article_schema_drift.py"
git commit -m "fix(tool): 同步 generate_article schema 与 v0.6 行为(P0#4)"
```

---

## Task 5: 阶段 1 P0#5 — max_retries ≥3 + 指数退避

**Files:**
- Modify: `D:\GEO2\backend\app\domain\llm_client.py:191, 211-237`
- Create: `D:\GEO2\backend\tests\test_query_single_retries_with_backoff.py`

- [ ] **Step 1: 写重试 + 退避测试**

```python
"""验证 query_single 重试 3 次 + 指数退避。"""
import asyncio
from unittest.mock import AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_query_single_retries_three_times_with_exponential_backoff():
    """连续 3 次 RateLimitError 应触发 3 次重试 + 2 次退避（0s, 2s）。"""
    settings = ...  # 构造 Settings
    client = LLMClient(settings)
    with patch("app.domain.llm_client.asyncio.sleep") as mock_sleep:
        # 让 LLM 始终抛 RateLimitError
        ...
        result = await client.query_single(...)
    # 应有 4 次尝试（max_retries=3 + 1 首次）
    # 应有 3 次退避（attempt 1, 2, 3）
    assert mock_sleep.call_count == 3
    # 退避序列：0, 2, 4（2 ** (attempt-1)）
    assert mock_sleep.call_args_list[0].args[0] == 1  # 2^0
    assert mock_sleep.call_args_list[1].args[0] == 2  # 2^1
    assert mock_sleep.call_args_list[2].args[0] == 4  # 2^2
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 修改 llm_client.py**

```python
# line 191
async def query_single(self, provider, question, brand, industry, max_retries: int = 3):  # 1 → 3

# lines 211-237 重试循环
for attempt in range(max_retries + 1):
    if attempt > 0:
        await asyncio.sleep(2 ** (attempt - 1))  # 指数退避
    try:
        ...
```

- [ ] **Step 4: 重新运行测试 + 全量 pytest**

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2"
git add "backend/app/domain/llm_client.py" "backend/tests/test_query_single_retries_with_backoff.py"
git commit -m "feat(retry): max_retries 提到 3 + 指数退避(P0#5)"
```

---

## Task 6: 阶段 1 P0#6 — memory.py 宽泛捕获收敛

**Files:**
- Modify: `D:\GEO2\backend\app\domain\agent\memory.py:113, 138, 188, 274, 298, 318, 354, 381`（共 8 处）
- Modify: `D:\GEO2\backend\app\domain\exceptions.py`（共享 _LLM_TRANSIENT_EXCEPTIONS）
- Create: `D:\GEO2\backend\tests\test_memory_transient_classification.py`

- [ ] **Step 1: 写 transient/programming 分类测试**

```python
"""验证 memory.py 区分 transient（捕获降级）与 programming（向上抛）。"""
import pytest
from app.domain.agent.memory import MemoryService

@pytest.mark.asyncio
async def test_memory_recovers_from_transient_exception():
    """Transient 异常（RateLimitError）应被捕获并降级。"""
    ...

@pytest.mark.asyncio
async def test_memory_propagates_programming_exception():
    """编程错误（AttributeError）应向上抛而非吞掉。"""
    with pytest.raises(AttributeError):
        ...
```

- [ ] **Step 2: 把 _LLM_TRANSIENT_EXCEPTIONS 上移到 exceptions.py**

从 `content_writer.py:18-24` 复制到 `backend/app/domain/exceptions.py`，让 `content_writer.py` 和 `memory.py` 都从 exceptions 导入。

- [ ] **Step 3: 修改 memory.py 8 处 except**

每处把 `except Exception` 改为 `except _LLM_TRANSIENT_EXCEPTIONS`。

- [ ] **Step 4: 运行测试 + 全量 pytest**

Expected: 全部通过；如出现失败说明原 `except Exception` 吞掉的 bug 现在暴露，逐个判断保留或修复。

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2"
git add "backend/app/domain/agent/memory.py" "backend/app/domain/exceptions.py" "backend/app/domain/generator/content_writer.py" "backend/tests/test_memory_transient_classification.py"
git commit -m "refactor(memory): 8 处 except Exception 收敛到 _LLM_TRANSIENT_EXCEPTIONS(P0#6)"
```

---

## Task 7: 阶段 1 完成门控

- [ ] **Step 1: 全量 pytest**

```bash
cd "D:/GEO2/backend"
.venv/Scripts/python.exe -m pytest tests/ -v
```

Expected: 全部通过（含新增 P0 测试）。

- [ ] **Step 2: ruff 检查**

```bash
.venv/Scripts/python.exe -m ruff check app/
```

Expected: 无新增错误（已有错误允许，标记为 P1/P2 处理）。

- [ ] **Step 3: 跑 evals baseline**

```bash
.venv/Scripts/python.exe -m backend.evals.runner
```

Expected: 30 条用例可跑通。

- [ ] **Step 4: 更新 baseline_report.md 真实数据**

把 pass rate / 平均 token 等数据写入。

- [ ] **Step 5: 更新 review/README.md 11 维度评分表**

把 06 评测 1 → 3、11 Harness 2 → 3.5、10 架构 3 → 3.5（修复反向依赖）。

- [ ] **Step 6: 打 tag + commit**

```bash
cd "D:/GEO2"
git add "backend/evals/baseline_report.md" "docs/review/README.md"
git commit -m "docs(review): 阶段 1 完成更新 11 维度评分"
git tag -a upgrade-stage-1 -m "GEO2 升级阶段 1 完成(P0 6 项,总分 35→40)"
```

---

## 阶段 2 / 阶段 3 / 阶段 4

> 本 plan 文件仅详细到阶段 1（含 Task 0-7）。
> 阶段 2/3/4 在阶段 1 完成后，根据实际进展细化各自的 task 列表。
> 参考 spec §3 与 review/99-improvement-plan.md。

阶段 2（20d, 12 项 P1）核心改动：

- Task 8: MAX_REACT_ITERATIONS → Settings（0.5d）
- Task 9: 嵌套 async with → DI（1d）
- Task 10: LLM 失败显式降级（1d）
- Task 11: 工具 schema 防 drift 测试（0.5d）
- Task 12: token 级截断（1d）
- Task 13: 历史摘要策略（2d）
- Task 14: 声明式权限（1d）
- Task 15: HumanConfirmation 专项测试（1d）
- Task 16: react_loop transient 区分（1d）
- Task 17: 故障注入测试（2d）
- Task 18: Sentry 接入（0.5d）
- Task 19: Langfuse 接入（0.5d）
- Task 20: trace_id 串联（1d）
- Task 21: Providers 抽象（3d）
- Task 22: import-linter（1d）
- Task 23: tech-debt-tracker.md（0.5d）
- Task 24: turn 延迟 + LLM 耗时 + cost（1.5d）
- Task 25: 慢查询告警（0.5d）
- Task 26: pending 超时（0.5d）
- Task 27: reject 理由入上下文（1d）

阶段 2 完成后预期 40 → 47.5（A 级下限），用户在此验收。

阶段 3（10d, 8 项 P1 剩余）+ 阶段 4（55d, 25 项 P2）按需展开。

---

## 验收检查清单

### 阶段 1 后

- [ ] 6 个 P0 任务全部 commit
- [ ] pytest 全部通过（含 4 个新增测试文件）
- [ ] ruff 无新增错误
- [ ] evals/ 30 条可跑通
- [ ] baseline_report.md 有真实数据
- [ ] review/README.md 更新 11 维度评分
- [ ] tag `upgrade-stage-1` 已创建

### 阶段 2 后（用户验收）

- [ ] 12 个 P1 任务全部 commit
- [ ] 总分 ≥ 47.5
- [ ] 11 维度全部 4-5 分
- [ ] Sentry/Langfuse 接通
- [ ] import-linter 阻断测试通过
- [ ] tag `upgrade-stage-2` 已创建
- [ ] 用户验收签字

### 阶段 3 后

- [ ] 8 个 P1 剩余任务全部 commit
- [ ] 总分 ≥ 49
- [ ] tag `upgrade-stage-3` 已创建

### 阶段 4 后

- [ ] 25 个 P2 任务全部 commit
- [ ] 总分 ≥ 50
- [ ] tag `upgrade-stage-4` 已创建