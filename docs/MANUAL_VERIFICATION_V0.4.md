# 手动验证清单 — GEO Agent v0.4

发布前必跑 8 个场景。

## 前置条件

```bash
cd "D:/GEO2"
docker-compose up --build -d
sleep 30
```

确认：
- 后端 `http://localhost:8000/health` 返回 `{"status":"ok"}`
- 前端 `http://localhost:5173/agent` 页面可访问

## 场景

### 1. 完整诊断流程 ✅

1. 进入 `/agent` → 点击"+ 新建对话"
2. 输入"诊断小米"
3. **预期**：
   - 看到 agent 文字响应（"好的，让我先诊断..."）
   - 看到"正在调用 diagnose_brand..." 卡片
   - 看到工具结果卡片（overall_score 等）
   - 最终 agent 总结（"小米 GEO 分数 XX..."）
   - 历史 session 列表中标题自动变为"诊断小米"或类似

### 2. 完整生成流程 ✅

1. 创建新对话
2. 输入"帮我生成一篇关于小米手机的评测文章"
3. agent 先调 `search_knowledge` 查资料
4. agent 调 `generate_article` → 弹窗"准备生成文章：品牌：小米 / 主题：..."
5. 点"确认"
6. **预期**：
   - 工具结果返回（status: generated, title, content_preview, word_count）
   - agent 总结（"已生成文章，请到 /tasks/new 触发完整流程"）

### 3. 用户取消生成 🛑

1. 创建新对话
2. 输入"生成文章"
3. 弹窗出现
4. 点"取消"
5. **预期**：agent 回应"好的，已取消。"

### 4. 多 session ✅

1. 创建 3 个独立对话（不同内容）
2. **预期**：每个 session 独立保存历史，互不干扰

### 5. 历史回看 ✅

1. 创建 session，发送几条消息
2. 离开页面（关闭浏览器）
3. 重新打开 `/agent/{sessionId}`
4. **预期**：完整历史可见，包括所有 assistant 消息和工具调用

### 6. SSE 流式渲染 ✅

1. 发送一条会触发多轮工具调用的消息
2. **预期**：消息逐条出现（不是等全部完成才显示）

### 7. LLM 失败处理 ⚠️

1. 编辑 `.env`：`DEEPSEEK_API_KEY=sk-invalid`
2. `docker-compose restart backend`
3. 发送消息
4. **预期**：显示"AI 服务暂时不可用"类提示（或 SSE 提前结束）

### 8. human-in-the-loop 跨刷新 ✅

1. 创建对话，触发 `generate_article` → 弹窗
2. **不要**点确认，**刷新页面**
3. 重新打开对话
4. **预期**：弹窗状态保持（或消息列表显示"待确认"标记），用户可继续

## 通过标准

8 项全过 → v0.4 完成。

## 已知限制（v0.4 不做）

- ❌ 多用户系统 / 鉴权 / 团队（推到 v1.0）
- ❌ 写类工具直接落库到 v0.2 系统（agent 只读 + 只预览）
- ❌ 多 Agent 协作 / Agent 通信
- ❌ LangChain / LangGraph / Claude SDK（v0.4 用 OpenAI SDK + 自己写 ReAct）
- ❌ MCP server 暴露
- ❌ 流式 LLM 输出（v0.4 用 SSE 但 LLM 响应一次性）

## 故障排查

- 端点 404：检查 `app/main.py` 是否注册了 `agent_sessions` 和 `agent_chat` router
- SSE 不流：检查 FastAPI `StreamingResponse(media_type="text/event-stream")`
- 表不存在：检查 conftest 已 import `app.models.orm_v04`
- LLM 不返回 tool_call：检查 `LLMClient.chat_with_tools` 用的是 `tools=TOOLS` 不是裸 list