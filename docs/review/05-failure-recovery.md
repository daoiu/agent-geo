# 05. 失败恢复

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

工具失败、超时、网络错误的降级与重试。包括：try/except + 重试、降级回答模板、故障注入测试、可重放、可恢复会话。

依据：[`00-learning-summary.md` §6.5](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 失败即崩溃 |
| 1 | 雏形 | 仅有 print/error |
| 2 | 基础 | 有 try/except 但无降级 |
| 3 | 达标 | try/except + 重试 |
| 4 | 良好 | 降级模板 + 故障注入测试 |
| 5 | 卓越 | 可重放 + 可恢复会话 + 显式 transient/programming 区分 |

## 3. GEO2 现状调研

### 3.1 显式 transient/programming 区分（强项）

来源：[`content_writer.py` L15–L24](./../backend/app/domain/generator/content_writer.py)

```python
# Exceptions that should be silently absorbed as "LLM failure" (caller
# marks article as errored). Programming errors propagate so we don't
# hide real bugs.
_LLM_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    asyncio.TimeoutError,
    APITimeoutError,
    RateLimitError,
    APIError,
    httpx.HTTPError,
)
```

**优点**：

- ✓ 显式定义 transient 异常（asyncio.TimeoutError / APITimeoutError / RateLimitError / APIError / httpx.HTTPError）
- ✓ 注释明确哲学："Programming errors propagate so we don't hide real bugs"
- ✓ 同时存在于 `content_writer.py` 和 `content_writer_agent.py`

这是**难得的工程纪律** —— 大多数项目都是 `except Exception`，GEO2 显式区分。

### 3.2 LLMClient.query_single 重试 + 降级（达标）

来源：[`llm_client.py` L185–L246](./../backend/app/domain/llm_client.py)

```python
async def query_single(self, provider, question, brand, industry, max_retries: int = 1):
    ...
    for attempt in range(max_retries + 1):
        try:
            ...
            response = await asyncio.wait_for(client.chat.completions.create(...), timeout=...)
            return self._parse_answer(...)
        except asyncio.TimeoutError:
            last_error = "timeout"
            logger.warning("llm_timeout", provider=provider, attempt=attempt)
        except LlmError as e:
            last_error = str(e)
            if not e.retryable:
                break
            logger.warning("llm_error", provider=provider, attempt=attempt, error=e)
        except (httpx.HTTPError, Exception) as e:  # noqa: BLE001
            last_error = f"{type(e).__name__}: {e}"
            logger.warning("llm_unexpected", provider=provider, attempt=attempt, error=last_error)

    return MentionResult(
        question=question,
        llm_provider=provider,
        llm_answer="",
        brand_mentioned=False,
        sentiment="neutral",
        error=last_error,
    )
```

**优点**：

- ✓ 重试 + 降级（失败返回 MentionResult(error=...) 而非抛异常）
- ✓ 重试依据 retryable 标志
- ✓ 每次 attempt 都有 warning 日志

**弱项**：

- ✗ `max_retries=1` 默认值偏小（生产建议 ≥3）
- ✗ 无指数退避（连续立即重试）
- ✗ 倒数第二行 `(httpx.HTTPError, Exception)` 仍是宽泛捕获（虽然有 noqa）
- ✗ 不区分 LlmError 重试与 httpx 错误重试（都用同一 max_retries）

### 3.3 工具调用失败：不破坏 Loop（强项）

来源：[`react_loop.py` L352–L393](./../backend/app/domain/agent/react_loop.py)

```python
try:
    result = await executor.execute(tool_name, tool_args)
except Exception as exc:
    from app.domain.exceptions import HumanConfirmationRequired

    if isinstance(exc, HumanConfirmationRequired):
        _emit_metrics(agg, ..., "human_confirmation")
        yield {"event": "human_confirmation_required", ...}
        return

    err_payload = {"error": f"{type(exc).__name__}: {exc}"}
    async with factory() as session:
        repo = AgentRepository(session)
        await repo.create_message(
            session_id=session_id, role="tool",
            content=json.dumps(err_payload, ensure_ascii=False),
            tool_call_id=tool_id,
        )
    yield {"event": "tool_call_result", "result": err_payload}
    continue  # 继续下一轮
```

**优点**：

- ✓ 失败包装为 tool 消息（LLM 可看到错误并决策下一步）
- ✓ 不中断 Loop（continue）
- ✓ 异常类型名包含在错误消息（便于 LLM 理解）
- ✓ HumanConfirmationRequired 单独处理（暂停 + 等待用户）

**弱项**：

- ✗ 无重试（工具失败直接包装）
- ✗ `except Exception` 宽泛捕获（应区分 transient / programming）
- ✗ 无 `_LLM_TRANSIENT_EXCEPTIONS` 类似的白名单（这里没有 transient 区分）

### 3.4 多层降级模板（强项）

| 路径 | 失败模式 | 降级策略 | 来源 |
| --- | --- | --- | --- |
| LLMClient.query_single | LLM 失败 | 返回 MentionResult(error=...) | [`llm_client.py` L239–L246](./../backend/app/domain/llm_client.py) |
| content_writer._extract_title | LLM 失败 | 返回 `("", "")` 标记错误 | [`content_writer.py` L89–L90](./../backend/app/domain/generator/content_writer.py) |
| session_manager.auto_generate_title | LLM 失败 | fallback 到消息截断 | [`session_manager.py` L26, L39–L41](./../backend/app/domain/agent/session_manager.py) |
| ReAct Loop 工具调用 | 工具失败 | 包装成 tool 消息 | [`react_loop.py` L367–L380](./../backend/app/domain/agent/react_loop.py) |
| tool_executor._execute_create_generation_task | SQLAlchemyError | 静默吞掉 | [`tool_executor.py` L249](./../backend/app/domain/agent/tool_executor.py) |

**优点**：

- ✓ 每个失败路径都有降级策略
- ✓ 降级返回值带 error 信息（便于上层决策）

**弱项**：

- ✗ 部分降级静默（tool_executor._execute_create_generation_task 的 SQLAlchemyError 仅返回错误字典，无日志）

### 3.5 内存服务的失败处理（弱项）

来源：[`memory.py` 多处 except Exception](./../backend/app/domain/agent/memory.py)

```python
# memory.py L115, L147, L197, L282, L304, L321, L362, L385 — 8 处 except Exception
except Exception as e:  # noqa: BLE001
    logger.warning(...)
```

**问题**：

- ✗ 8 处 `except Exception # noqa: BLE001` —— 宽泛捕获
- ✗ 与 content_writer 的纪律不一致（后者有 _LLM_TRANSIENT_EXCEPTIONS）
- ✗ 编程错误（KeyError、TypeError）被静默吞掉，调试困难

### 3.6 故障注入测试

来源：[`backend/tests/`](./../backend/tests/) —— 没有 `test_failure_recovery.py` 或 `test_fault_injection.py`。

失败路径测试分散在：
- `test_llm_chat_with_tools.py`（LLM 调用）
- `test_api_agent_chat.py`（API 错误路径）
- 各 `test_tool_executor_*.py`（工具错误）

**缺口**：没有统一的故障注入测试套件。

### 3.7 可重放 / 可恢复

- ✓ DB 历史持久化（messages 表）—— 可读取历史
- ✓ run_agent_turn_from_checkpoint —— 可从 pending_confirmation 恢复
- ✗ 无显式 replay API（基于历史重放整个 turn）
- ✗ 无断点 replay（从任意中间步骤重放）

## 4. 评分与理由

**评分：4 / 5（良好）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| try/except + 重试 | ✓ LLMClient 有（max_retries=1） | +1 |
| 降级模板 | ✓ 多层降级（mention_result / fallback content / fallback title） | +1 |
| 不破坏 Loop | ✓ 工具失败包装成 tool 消息 | +1 |
| Transient/programming 区分 | ✓ content_writer 显式，react_loop/memory 未一致 | +0.5 |
| 故障注入测试 | ✗ 无 | - |
| 可重放 | ✗ 无 replay API | - |
| 指数退避 | ✗ 无 | - |

**关键证据**：

- 强项：transient 区分哲学、降级模板、Loop 不中断
- 弱项：max_retries=1、无指数退避、memory.py 宽泛捕获、无故障注入测试

**与行业标准差距**：

- 与 LangChain 比：缺统一 retry policy
- 与生产级标准（3 次重试 + 指数退避）：当前不够
- 与内部"卓越"标准：缺 replay / 故障注入

## 5. 面试讲点

### 30 秒版本

> 显式 _LLM_TRANSIENT_EXCEPTIONS 区分业务/编程错误；LLMClient 重试 + 降级到 MentionResult；工具失败包装成 tool 消息不破坏 Loop；多层降级模板。

### 2 分钟版本

1. **核心哲学**：
   - `_LLM_TRANSIENT_EXCEPTIONS` 显式区分（asyncio.TimeoutError / RateLimitError / APIError / httpx）
   - 注释：Programming errors propagate so we don't hide real bugs
2. **三层降级**：
   - LLMClient.query_single → MentionResult(error=...)
   - content_writer._extract_title → ("", "")
   - session_manager.auto_generate_title → 消息截断
3. **Loop 不中断**：工具失败包装成 tool 消息，LLM 可看到错误继续决策
4. **断点恢复**：run_agent_turn_from_checkpoint 从 pending_confirmation 恢复

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 重试几次？ | 默认 max_retries=1（即 2 次尝试）；生产可调到 3 |
| 有指数退避吗？ | 没有（**改进候选**） |
| 工具失败能重试吗？ | 当前不能直接重试；可让 LLM 重新调（**改进候选**） |
| 编程错误怎么发现？ | 依赖 structlog warning 日志；memory.py 多处静默吞（**改进候选**） |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P0 | max_retries 默认值提到 ≥3 + 指数退避（与 _LLM_TRANSIENT_EXCEPTIONS 配合） | 见 `99-improvement-plan.md` |
| P0 | memory.py 多处宽泛捕获收敛到 _LLM_TRANSIENT_EXCEPTIONS 模式 | 见 `99-improvement-plan.md` |
| P1 | react_loop 工具失败引入 transient/programming 区分 | 见 `99-improvement-plan.md` |
| P1 | 故障注入测试套件（mock LLM 抛 RateLimitError 等） | 见 `99-improvement-plan.md` |
| P2 | 显式 replay API（基于历史重放 turn） | 见 `99-improvement-plan.md` |