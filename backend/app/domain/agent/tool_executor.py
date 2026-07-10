"""v0.4 ToolExecutor：包装 v0.1-v0.3 业务逻辑执行 Agent 工具调用。

工具分类：
- 读类（直接执行）：diagnose_brand、search_knowledge
- 写类（抛 HumanConfirmationRequired 暂停 ReAct 循环）：generate_article

设计原则：
- 不修改 v0.1-v0.3 代码，只包装
- 参数由 validate_tool_args 在 dispatch 前校验
- 写类工具仅持久化"待确认"消息，不直接调 ContentWriter
- 写类工具的真实执行在 ToolExecutor._execute_generate_article_confirmed 中
  （由 confirm_action 端点触发，从断点续跑）
"""
from __future__ import annotations

import structlog

from app.domain.agent.tools import (
    DiagnoseBrandArgs,
    GenerateArticleArgs,
    SearchKnowledgeArgs,
    validate_tool_args,
)

logger = structlog.get_logger()


class ToolExecutor:
    """执行 Agent 工具调用。

    封装 v0.1（DiagnosisService）、v0.2（KnowledgeRepository、ContentWriter）。
    写类工具抛 HumanConfirmationRequired 暂停 ReAct 循环。
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    async def execute(self, tool_name: str, args: dict) -> dict:
        """参数校验后分发到对应执行方法。

        Raises:
            ValueError: 未知工具。
            pydantic.ValidationError: 参数不合法。
            HumanConfirmationRequired: 写类工具，需要人工确认。
        """
        # 先校验参数
        validated = validate_tool_args(tool_name, args)

        if tool_name == "diagnose_brand":
            return await self._execute_diagnose_brand(validated)
        if tool_name == "search_knowledge":
            return await self._execute_search_knowledge(validated)
        if tool_name == "generate_article":
            return await self._execute_generate_article(validated)

        raise ValueError(f"Unknown tool: {tool_name}")

    async def _execute_diagnose_brand(self, args: DiagnoseBrandArgs) -> dict:
        """诊断品牌。包装 v0.1 DiagnosisService。"""
        # 完整实现在 Task 2.2
        raise NotImplementedError

    async def _execute_search_knowledge(self, args: SearchKnowledgeArgs) -> dict:
        """搜索知识库。包装 v0.2 KnowledgeRepository。"""
        # 完整实现在 Task 2.3
        raise NotImplementedError

    async def _execute_generate_article(self, args: GenerateArticleArgs) -> dict:
        """生成文章（待确认）。

        落"待确认"消息到 agent_messages，抛 HumanConfirmationRequired 暂停 ReAct。
        真实生成在 _execute_generate_article_confirmed 中（confirm_action 后触发）。
        """
        # 完整实现在 Task 2.4
        raise NotImplementedError

    async def _execute_generate_article_confirmed(
        self, args: GenerateArticleArgs, checkpoint_message_id: str
    ) -> dict:
        """写类工具确认后真正调 v0.2 ContentWriter。

        仅返回预览，不落库到 v0.2 系统。
        完整实现在 Phase 4 断点续跑（与 run_agent_turn_from_checkpoint 配合）。
        """
        raise NotImplementedError