# 简历 · 1 页纸版(目标岗位:AI Agent / AI 应用开发)

> v5 的精简投递版。完整面试弹药库(15 题答案 + 6 件事自检 + 5 问自检)保留在 `RESUME_GEO_Agent_v5.md`,不在简历里。

---

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[姓名]                                       目标岗位:AI Agent / AI 应用开发
电话:[手机]   邮箱:[邮箱]   GitHub:[github.com/xxx]
期望城市:[城市 / 接受远程]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【个人简介】
[1~3 / N] 年 Python 后端,近 [N] 年聚焦 LLM Agent 工程化。独立主导 GEO 优化
Agent 9 个迭代阶段(诊断→RAG→内容生成→审核发布→监测),6 个核心模块
~2 200 行、测试 1 100+ 行。所有模块都能讲清「为什么存在 / 失败怎么兜底
/ 效果怎么验证」,可 5 分钟 docker-compose 复现完整链路。

【技能清单】
• 语言与运行时:Python 3.11+、SQL、Shell、asyncio、类型注解
• Web 与 API:FastAPI、Uvicorn、Pydantic v2、StreamingResponse / SSE
• Agent 与编排:自写 ReAct 状态机(对标 LangGraph,不引框架)、
  Multi-Agent(主 agent + ContentWriter / Monitor 双 specialist)、
  Handoff 协议 5 条工程纪律(幂等键 / 超时 / 状态隔离 / 失败回退 / 成本归因)、
  OpenAI Function Calling、Pydantic 工具参数强校验、断点续跑 checkpoint
• 模型与网关:OpenAI 兼容 SDK(DeepSeek / DeepSeek-R1 / Kimi / MiniMax)、
  流式 chat.completions、推理模型 think 块治理
• 检索与 RAG:bge-small-zh-v1.5、ChromaDB、jieba、RRF 融合、降级与增量同步
• 记忆与上下文:ChromaDB 向量记忆层(scope 隔离 / 距离阈值去重)、
  上下文预算(滑动窗口 + 旧工具结果截断)
• 数据与缓存:SQLAlchemy 2 async、aiosqlite、APScheduler、structlog
• 前端:React 18 + TypeScript + Vite + Tailwind + Radix UI + Playwright
• 工程化:Docker、docker-compose、pytest + vitest + Playwright E2E

【项目经历】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GEO 优化 Agent(v0.1 → Phase 3)        [起始年月] – [结束年月]
个人项目 / 后端主导 + 前端 + 工程化
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**项目描述** 面向品牌 GEO(生成式引擎优化)的 AI Agent 平台,服务非技术市场
人员,提供自然语言入口完成"诊断 → RAG 检索 → 内容生成 → 审核发布 →
提及率监测"端到端闭环;9 个迭代阶段、188 个 commit、Docker 一键起服务。

**核心职责(围绕 6 件事 · 工程师写法)**

1. **任务边界(替谁 / 做什么 / 不做什么)** — 替非技术市场人员做 GEO
   诊断 + 内容生成辅助 + 发布辅助 + 监测;不做内容伪造 / AI 投毒 /
   黑帽 SEO(README §9 合规说明)。Agent 入口仅自然语言对话,5 工具覆盖
   诊断 / 检索 / 列库 / 单篇生成 / 批量任务。

2. **工具契约(参数 / 失败 / 回退)** — 5 工具入参用 Pydantic 模型做强校验;
   跨 provider 切换时按 `kept_ids = resolved_ids ∩ declared_ids` 策略丢弃
   dangling tool_call、跳过孤儿 tool 结果,strict provider 0 失败。
   失败回退链:HybridSearch 失败 → 降级纯关键词;ContentWriter transient
   异常 → 吞掉返回空;主循环未捕获异常 → 转 JSON 错误载荷继续 ReAct;
   写工具默认后台异步(落 Task 表 + 触发 worker + 立即返回 task_id,
   与批量任务复用同一套路径)。

3. **上下文策略(什么进 / 什么先摘要 / 怎么防爆)** — Phase 3 上下文预算
   默认关闭可调:滑动窗口(默认 40 条)+ 旧工具结果截断(默认 2000 字,
   最近 3 个保全量);`build_messages` 先裁窗口再算 kept_ids,避免边界
   副作用。system prompt 分层:常量部分(角色 + 工具契约 + 反编造)在前,
   L2 记忆索引段(常量化利于 prompt cache)在末尾。

4. **状态管理(什么跨会话 / 什么用完即焚 / 怎么冲突)** — 三层存储:会话级
   `AgentMessageORM`(role / content / tool_calls / tool_call_id /
   pending_confirmation)用完即焚;跨会话级 `AgentMemoryORM`(4 类型受
   白名单约束:user / feedback / project / reference);向量层
   `MemoryVectorIndex`(ChromaDB 单 collection + scope 隔离,scope =
   device_id 跨 session 共享)。冲突处理:写入去重(字数门控 ≥8 + cosine
   距离阈值 0.15)+ 整理去重(consolidate 阈值 50 触发,同步 delete_scope
   + 回填向量)。

5. **权限确认(高风险动作怎么兜底)** — 写工具默认后台异步,与 v0.2 批量
   任务复用"用户在前端审核"兜底。HITL 路径 opt-in:写类工具抛
   `HumanConfirmationRequired` → ReAct 暂停 → yield SSE 事件 → 前端弹窗
   → 用户确认 → `run_agent_turn_from_checkpoint` 从 checkpoint 续跑。
   网络面:SSRF 守卫拒绝内部 IP(dev/prod 模式切换);WordPress 用
   Application Password;SMTP 密码加密存 SQLite。推理模型适配双层防御:
   静态正则剥离 + 流式三态状态机(`before_think → in_think → after_think`)
   + 7 字符回看缓冲 + system_prompts 显式禁止 think 块外泄。

6. **评测集(一次改动到底变好还是变差)** — `test_content_writer_agent.py`
   392 行(think 块静态剥离 + 流式跨 chunk 切断 102 行新增)+
   `test_tool_executor.py` 729 行(后台异步 + HITL 双路径覆盖)+ pytest +
   vitest + Playwright E2E。Phase 1 观测重构:`_emit_metrics` 在三出口
   (turn_complete / max_iterations_reached / human_confirmation)打
   `agent_turn_metrics` 结构化日志,聚合 prompt / completion / total token;
   配套 `agg_metrics.py` token baseline 脚本。诚实备注:个人项目无线上
   流量,但可现场跑 200 条品牌 GEO 真实问题采样,对照无 RAG / 有 RAG 的
   关键实体命中率 + 引用正确率 + 拒答率。

**项目成果** 9 个迭代阶段 / 6 个核心模块 / 188 个 commit;5 工具 / 4 模型
适配 / 单库 + 跨库双路径检索 / strict provider 0 失败;README +
MANUAL_VERIFICATION_V0.1~V0.5 + 设计 / 实施 / 验证三套文档完整,可作为
团队新人 onboarding 材料。

【教育背景】
[学校] · [专业] · [学士 / 硕士] · [起始年月] – [结束年月]
• [GPA / 荣誉 / 相关课程,可选]

【其他】
• 技术博客 / 开源:[链接,可选]
• 英文:[CET-6 / 雅思 / 托福,可选]
```

---

## 📋 v5_1page vs v5 对照

| 维度 | v5(454 行) | v5_1page(本文件,~80 行) |
|---|---|---|
| 抬头 / 简介 / 技能 | ✅ | ✅(完全保留) |
| 项目经历 | 6 件事各 1 节 + 长文 | 6 件事合并为 1 个紧凑块,每件事 1 段 |
| 项目成果 | 单独成段 | 合并到项目经历末尾 |
| 15 题自检答案 | ✅(面试弹药) | ❌(留在 v5) |
| 6 件事 / 5 问自检 | ✅ | ❌(留在 v5) |
| 保守边界 | ✅ | ❌(口头应对,不写简历) |
| **投递使用** | 信息过载,容易被 HR 秒拒 | **直接复制** |

## 🚀 投递前 30 秒核对

1. **[占位符] 全部替换**:`[姓名]` `[手机]` `[邮箱]` `[学校]` `[起始年月]` 等
2. **JD 关键词对齐**:JD 写 LangGraph / Multi-Agent / MCP 时,调整对应 bullet 措辞
3. **诚实备注不强写**:`诚实备注:个人项目无线上流量` 留在面试应对,简历里只写"9 个迭代阶段、5 工具 / 4 模型 / strict provider 0 失败"等可验证数据
4. **PDF 标准自检**:扫一眼每条 bullet,确认是「**针对 X 问题,基于 X 机制,设计 X 方案,实现 X 效果**」句式,而不是「使用 X,实现 Y」的八股写法

需要更精简的英文版 / 某具体公司 JD 对齐版时,直接告诉我 JD 即可。