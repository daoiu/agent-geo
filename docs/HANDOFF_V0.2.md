# v0.2 实施启动话术

> **新会话复制下面整段即可启动 v0.2 实施**

---

```
按 D:/GEO2/docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.2.md
实施 GEO Agent v0.2（29 个 task：知识库 + 任务 + 生成 + 审核）。

前置条件：v0.1 代码已存在并测试通过。

流程：
1. 调 superpowers:using-superpowers skill
2. 读 plan + specs/2026-07-09-geo-agent-v0.2-design.md
3. 报告读完，问执行方式（subagent-driven / inline）
4. 简体中文回复，Conventional Commits，TDD 严格

约束：
- 复用 v0.1 的 LLMClient / FastAPI 单进程 / SQLite
- 不引入新依赖（jieba / pypdf / python-docx / markdown 都是新加的）
- 切片规则：50-500 字/片，按段落 + 句子边界
- 4 文件类型：pdf / docx / md / txt
- jieba 关键词搜索（v0.5 会升级到向量检索）
- 单进程 asyncio.Lock 共享（v0.1 已有）
- 任务状态机：pending → running → completed / failed / cancelled
- 写类工具不直接落库到 v0.2 系统（agent 边界）
```

---

## 关键文件

| 文件 | 路径 | 用途 |
|---|---|---|
| 设计文档 | `docs/superpowers/specs/2026-07-09-geo-agent-v0.2-design.md` | v0.2 做什么 + 为什么 |
| 实施计划 | `docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.2.md` | 29 个 task 的 TDD 步骤 |
| 手动清单 | `docs/MANUAL_VERIFICATION_V0.2.md` | 发布前必跑 8 个场景 |
| v0.1 spec（前置）| `docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md` | 复用 LLMClient 等 |

## 关键决策摘要

- **范围**：知识库（4 文件类型）+ 任务调度 + AI 生成（基于知识库）+ 人工审核
- **方向转变**：原 ROADMAP 是"内容改写"，用户改为"系统级 GEO"（知识库底座 + RAG）
- **切片**：段落优先 + 句子边界 + 50-500 字
- **生成 prompt 强约束**：不得编造参考资料、引用标注、拒绝元话语
- **任务异步**：asyncio.create_task + 共享 lock

## 实施注意事项

- **Phase 0 任务 0.3 (ORM)**：4 张新表都加外键级联，**v0.1 已有 SQLAlchemy 异步模式直接复用**
- **Phase 1 parser**：每个文件类型独立解析器（test_parser.py），损坏文件抛 `DocumentParseError`
- **Phase 1 chunker**：核心算法是 `chunk_text(text, min_length=50, max_length=500)`
- **Phase 2 知识库 API**：上传走 multipart/form-data，**文件大小限制 50MB**（413 错误）
- **Phase 3 任务**：顺序生成（不并行）避免 LLM 配额超限
- **Phase 4 生成**：`generate_article` 是写类工具，**只生成内容不落库**（v0.4 agent 边界保持一致）
- **Phase 5 审核**：`reject` 必须带 note（422 校验）
- **Phase 6 前端**：沿用 v0.1 模式（Tailwind + shadcn/ui + React Query）
- **Phase 7 E2E**：必须测"完整流程"（创建 KB → 上传 → 解析 → 任务 → 生成 → 审核）

## 不要做的事

- ❌ 引入向量检索（推到 v0.5）
- ❌ 自动发布（推到 v0.3）
- ❌ 监测功能（推到 v0.3）
- ❌ 任务并行（保持顺序避免 LLM 配额问题）
- ❌ 写类工具直接落库到 v0.2 系统
