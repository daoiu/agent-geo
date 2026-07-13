# 10. 架构分层

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

代码分层是否清晰、层间依赖方向是否正确。包括：API/Service/Domain/Repository/Models 分层、横切关注点抽象、机械执行约束。

依据：[`00-learning-summary.md` §3, §4, §6.10](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 无分层 |
| 1 | 雏形 | 仅按文件名分目录 |
| 2 | 基础 | 有分层但有反向依赖 |
| 3 | 达标 | 层间依赖方向正确、跨层有显式接口 |
| 4 | 良好 | 横切关注点通过 Provider 抽象 |
| 5 | 卓越 | lint + 结构测试机械执行分层约束 |

## 3. GEO2 现状调研

### 3.1 整体分层结构（强项）

来源：[`backend/app/` 目录结构](./../backend/app/)

```
backend/app/
├── api/              # API 服务层（12 个 endpoint 文件）
├── core/             # 基础设施（config, db）
├── domain/           # 业务核心
│   ├── agent/        # Agent Loop + 工具 + 记忆
│   ├── generator/    # 内容生成
│   ├── knowledge/    # 知识库
│   ├── monitor/      # 监控
│   ├── notification/ # 通知
│   ├── publisher/    # 发布
│   ├── security/     # 安全
│   ├── llm_client.py
│   ├── crawler.py
│   ├── renderer.py
│   ├── scorer.py
│   └── exceptions.py
├── models/           # 数据模型（orm.py / orm_v02-v04）
├── repositories/     # 数据访问（7 个 repo）
├── services/         # 业务编排（5 个 service）
├── tasks/            # 后台任务（2 个 worker）
└── main.py
```

**评价**：

- ✓ **7 层分明**：api / core / domain / models / repositories / services / tasks
- ✓ **Domain 模块按子域组织**：agent / generator / knowledge / monitor / notification / publisher / security（DDD 风格）
- ✓ **ORM 多版本管理**：orm_v02-v04 保留演进历史

**对照学习路线 §3 工程分层**：

| 学习路线分层 | GEO2 对应 |
| --- | --- |
| API 服务层 | api/ |
| 会话管理 | domain/agent/session_manager |
| Agent 运行时 | domain/agent/react_loop |
| 工具层 | domain/agent/tools + tool_executor |
| 上下文工程 | domain/agent/memory + memory_vector |
| 观测层 | 各模块 structlog |
| 评测层 | ✗ 无 |

### 3.2 典型依赖关系（domain → repositories / services）

来源：[`tool_executor.py` L83–L84](./../backend/app/domain/agent/tool_executor.py)

```python
async def _execute_diagnose_brand(self, args: DiagnoseBrandArgs) -> dict:
    ...
    from app.repositories.report_repo import ReportRepository
    from app.services.diagnosis_service import DiagnosisService
    ...
    svc = DiagnosisService(
        repo=repo, crawler=crawler, llm=llm, settings=settings
    )
    await svc.run(task_id, req)
```

**评价**：

- 这是 **DDD 推荐模式**：domain 层调用 repository（数据访问）+ service（业务编排）
- 不算严格意义上的"分层违反"，而是"领域服务模式"
- ✓ lazy import（避免循环引用）

### 3.3 ⚠️ 发现分层违反

来源：[`knowledge_repo.py` L278](./../backend/app/repositories/knowledge_repo.py)

```python
async def ...:
    from app.services.hybrid_search import HybridSearch  # ← repository → service
```

**问题**：

- ✗ **repository 反向依赖 service** —— 违反"Repo → Service"方向
- ✗ repository 应该只关心数据访问，hybrid_search 是业务逻辑

**这是真实的分层违反**，需要标记。

### 3.4 Domain 调用后台任务

来源：[`tool_executor.py` L26, L284](./../backend/app/domain/agent/tool_executor.py)

```python
from app.tasks.task_worker import schedule_task
```

**评价**：

- ✗ Domain 层依赖 tasks 层（创建后台任务）
- 严格分层应该让 Service 层负责调用 tasks 层
- 但这是为简化流程的工程取舍，可接受

### 3.5 ORM 多版本演进（强项）

来源：[`models/orm_v04.py`](./../backend/app/models/orm_v04.py) + [`models/orm_v03.py`](./../backend/app/models/orm_v03.py) + [`models/orm_v02.py`](./../backend/app/models/orm_v02.py) + [`models/orm.py`](./../backend/app/models/orm.py)

**评价**：

- ✓ 4 个 ORM 版本文件（v0 / v02 / v03 / v04）保留演进历史
- ✓ 每个 Repository 引用特定版本（如 `knowledge_repo.py` 引用 `orm_v02`）
- ✓ 新加表用最新版本（v04）

**潜在问题**：

- ✗ 模型分散在 4 个文件，跨表 JOIN 查询维护成本高
- ✗ 没有 ORM 版本迁移脚本（如何从 v02 升到 v03？）

### 3.6 跨层抽象

**横切关注点（认证、遥测、功能开关）**：

- 认证：未发现（API 层无 auth 依赖）
- 遥测：各模块 structlog（散落）
- 功能开关：未发现

**评价**：

- ✗ 无显式 `Providers` 抽象（OpenAI §4 严格分层要求）
- ✗ 认证未实施（API 直接暴露）

### 3.7 机械执行约束

来源：[`backend/pyproject.toml`](./../backend/pyproject.toml) + [`backend/Dockerfile`](./../backend/Dockerfile)

**评价**：

- ✗ 无 import-linter / dependency-linter 配置
- ✗ 无结构测试（架构约束靠人维护）
- ✗ CI 不验证分层（重构可能引入分层违反无人发现）

### 3.8 测试覆盖视角的分层

来源：[`backend/tests/`](./../backend/tests/)

```
test_api_*.py           # API 层集成测试
test_agent_*.py         # Domain 层单元测试
test_agent_tool_*.py    # Tool Executor 单元测试
test_tool_executor.py   # Tool Executor 整体
```

**评价**：

- ✓ 单元测试按层组织（test_api_ / test_agent_）
- ✓ 测试金字塔合理（单元 + 集成）

## 4. 评分与理由

**评分：3 / 5（达标，但有违反 + 缺机械约束）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 分层清晰 | ✓ 7 层分明 + DDD 子域 | +1 |
| Domain → Repo/Service | ✓ DDD 模式 | +1 |
| 依赖方向大致正确 | ✓ api → services → domain → repos → models | +1 |
| ORM 演进管理 | ✓ 多版本文件 | +0.5 |
| 无反向依赖 | ✗ knowledge_repo → hybrid_search | -0.5 |
| 显式 Providers 抽象 | ✗ 无 | - |
| 机械执行约束 | ✗ 无 lint / 结构测试 | - |
| 认证 | ✗ API 无 auth | - |

**关键证据**：

- 强项：7 层分明 + DDD 子域 + 多 ORM 版本
- 弱项：knowledge_repo 反向依赖 + 无机械约束 + 无认证

**与行业标准差距**：

- 学习路线 §3/§4：分层 + 严格方向 + 机械执行
- GEO2 处于"达标"档（层间方向正确），但缺"良好"和"卓越"档的关键能力

## 5. 面试讲点

### 30 秒版本

> 7 层分明（api/core/domain/models/repositories/services/tasks）+ DDD 子域划分；ORM 多版本管理演进历史；缺反向依赖（knowledge_repo → hybrid_search）+ 缺机械执行约束。

### 2 分钟版本

1. **整体架构**：
   - 7 层：API → Services → Domain → Repositories → Models
   - Domain 按子域组织（agent / generator / knowledge / monitor 等）
2. **典型调用链**：API → Domain → Repositories → Models
3. **ORM 演进**：4 个版本文件（v0/v02/v03/v04），保留演进历史
4. **已识别的分层违反**：
   - knowledge_repo 反向依赖 services/hybrid_search
   - Domain 直接调用 tasks/task_worker（设计取舍）
5. **改进方向**：
   - 加 import-linter 机械约束
   - 修复 knowledge_repo 反向依赖
   - 引入 Providers 抽象

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 为什么有 4 个 ORM 文件？ | v0.1-v0.6 演进历史；每个版本保留特定表，新表用最新 |
| Domain 为什么能调 Repository？ | DDD 模式：领域服务调用仓储是标准做法（不算违反） |
| knowledge_repo 反向依赖严重吗？ | 一处，已识别；可以重构（hybrid_search 提到 service 层） |
| 有 import-linter 吗？ | 没有（**改进候选 P1**） |
| 认证在哪？ | 当前 API 无 auth（**改进候选**） |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P0 | 修复 knowledge_repo → services/hybrid_search 反向依赖 | 见 `99-improvement-plan.md` |
| P1 | 引入 import-linter 机械约束（api → services → domain → repos → models） | 见 `99-improvement-plan.md` |
| P1 | 显式 Providers 抽象（auth / telemetry / feature flag） | 见 `99-improvement-plan.md` |
| P2 | ORM 版本迁移脚本（v02 → v03 → v04） | 见 `99-improvement-plan.md` |
| P2 | API 层加 auth 依赖（最小实现即可） | 见 `99-improvement-plan.md` |