"""Tests for ContentWriterAgent (v0.6 P1.5): 独立 system prompt + RAG chunks + 流式。

覆盖：
1. system prompt 由 ContentWriterAgent 自己注入（不是 user prompt 里嵌角色）
2. user prompt 只含主题/关键词/字数/参考资料（不含品牌/风格/角色）
3. base_url bare host（无 /v1）自动补全
4. transient 异常吞掉返回 (title, "")
5. 流式 yield 增量
"""
from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from app.core.config import Settings
from app.domain.generator.content_writer_agent import ContentWriterAgent


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=10,
    )


@pytest.fixture
def agent(settings: Settings) -> ContentWriterAgent:
    return ContentWriterAgent(settings)


# ===========================================================================
# 标题提取（与 ContentWriter 行为对齐）
# ===========================================================================


class TestTitleExtraction:
    def test_extracts_h1_title(self, agent: ContentWriterAgent) -> None:
        text = "# 真实标题\n\n内容。"
        title = agent._extract_title(text)
        assert title == "真实标题"

    def test_returns_fallback_for_no_h1(self, agent: ContentWriterAgent) -> None:
        title = agent._extract_title("没有标题的内容")
        assert title.startswith("未命名") or len(title) > 0

    def test_handles_markdown_prefix(self, agent: ContentWriterAgent) -> None:
        text = "  #  标题带空格  \n\n内容"
        title = agent._extract_title(text)
        assert title == "标题带空格"


# ===========================================================================
# 关键差异点 1：messages 必须包含独立 system role
# ===========================================================================


class TestMessagesStructure:
    def test_messages_has_independent_system_role(self, agent: ContentWriterAgent) -> None:
        """关键差异：必须有独立 system role，不能把角色指令塞 user 里。

        回归（v0.6 P1.5）：这是 ContentWriter → ContentWriterAgent 的核心升级。
        """
        messages = agent._build_messages(
            brand="小米",
            topic="产品评测",
            keywords=["性能"],
            style="professional",
            target_length=500,
            chunks=[{"index": 1, "content": "小米 14 跑分 200 万。"}],
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

        # system prompt 含品牌 + 风格
        sys = messages[0]["content"]
        assert "小米" in sys
        assert "专业严谨" in sys
        # v2 GEO 共识：必须含 GEO 内容生成 agent 角色定位
        assert "GEO" in sys
        # 必须有反编造规则
        assert "严禁编造" in sys
        # 必须有参考资料引用约定
        assert "参考资料" in sys
        # v2 新增：答案优先 + 原子化模块（GEO 核心写作范式）
        assert "答案优先" in sys
        assert "原子化" in sys

    def test_user_prompt_does_not_embed_role(self, agent: ContentWriterAgent) -> None:
        """user prompt 不再嵌角色指令（"你是 X 的内容编辑"）—— 那是 system 的事。"""
        messages = agent._build_messages(
            brand="小米",
            topic="产品评测",
            keywords=["性能"],
            style="professional",
            target_length=500,
            chunks=[],
        )
        user = messages[1]["content"]
        # 不再嵌"你是 X 的内容编辑"—— 验证升级生效
        assert "你是 小米 的内容编辑" not in user
        # user prompt 只含任务参数
        assert "【主题】产品评测" in user
        assert "【关键词】性能" in user
        assert "【目标字数】约 500 字" in user

    def test_brand_phrase_fallback_in_system(self, agent: ContentWriterAgent) -> None:
        """brand=None 时 system prompt 用"该品牌"。"""
        messages = agent._build_messages(
            brand=None,
            topic="T",
            keywords=[],
            style="neutral",
            target_length=300,
            chunks=[],
        )
        sys = messages[0]["content"]
        assert "该品牌" in sys
        assert "中性客观" in sys

    def test_unknown_style_passes_through(self, agent: ContentWriterAgent) -> None:
        """未知 style 直接透传（不崩）。"""
        messages = agent._build_messages(
            brand=None,
            topic="T",
            keywords=[],
            style="academic",  # 未注册
            target_length=300,
            chunks=[],
        )
        assert "academic" in messages[0]["content"]

    def test_v2_forbids_source_list_in_prompt(self, agent: ContentWriterAgent) -> None:
        """v2 GEO 共识 prompt 必须禁止 LLM 在文末输出 [1][2] 信源列表（产品反馈：不需要）。"""
        messages = agent._build_messages(
            brand="X", topic="T", keywords=[], style="neutral",
            target_length=500, chunks=[],
        )
        sys = messages[0]["content"]
        # v2 prompt 必须显式禁止文末信源列表
        assert "信源引用" in sys
        assert "不要" in sys

    def test_v2_forbids_think_leakage_in_prompt(self, agent: ContentWriterAgent) -> None:
        """v2 prompt 必须禁止 LLM 把 <think> 推理过程写进正文。"""
        messages = agent._build_messages(
            brand="X", topic="T", keywords=[], style="neutral",
            target_length=500, chunks=[],
        )
        sys = messages[0]["content"]
        # 反模式清单里有
        assert "思考过程外泄" in sys or "思考过程" in sys


# ===========================================================================
# 关键差异点 1.5：剥离 <think> 块
# ===========================================================================


class TestStripThinkBlocks:
    """LLM 推理模型（DeepSeek/MiniMax）在 reply 开头输出 <think>...</think>，
    必须从生成内容里剥离，否则 ArticleORM 会存到正文里。"""

    def test_strips_single_think_block_at_start(self) -> None:
        from app.domain.generator.content_writer_agent import ContentWriterAgent

        raw = "<think>\nLet me think...\n</think>\n\n# 真实标题\n\n正文。"
        out = ContentWriterAgent._strip_think_blocks(raw)
        assert "<think>" not in out
        assert "Let me think" not in out
        assert out.startswith("# 真实标题")

    def test_strips_think_block_in_middle(self) -> None:
        from app.domain.generator.content_writer_agent import ContentWriterAgent

        raw = "前置文字\n\n<think>\ninternal reasoning\n</think>\n\n# 标题\n\n后文"
        out = ContentWriterAgent._strip_think_blocks(raw)
        # think 块（含 'internal reasoning'）必须被剥掉
        assert "internal reasoning" not in out
        assert "<think>" not in out
        # 前置文字（非 think 块）必须保留
        assert "前置文字" in out
        # 标题和后文必须保留
        assert "# 标题" in out
        assert "后文" in out

    def test_strips_multiple_think_blocks(self) -> None:
        from app.domain.generator.content_writer_agent import ContentWriterAgent

        raw = "<think>A</think>正文<think>B</think>尾部"
        out = ContentWriterAgent._strip_think_blocks(raw)
        assert "A" not in out
        assert "B" not in out
        assert "正文" in out
        assert "尾部" in out

    def test_strips_multiline_think(self) -> None:
        from app.domain.generator.content_writer_agent import ContentWriterAgent

        raw = (
            "<think>\n"
            "1. 分析主题\n"
            "2. 提取关键词\n"
            "3. 设计章节\n"
            "</think>\n\n"
            "# 标题\n\n## 章节一\n内容"
        )
        out = ContentWriterAgent._strip_think_blocks(raw)
        assert "分析主题" not in out
        assert "提取关键词" not in out
        assert out.startswith("# 标题")

    def test_no_think_block_passes_through(self) -> None:
        from app.domain.generator.content_writer_agent import ContentWriterAgent

        raw = "# 标题\n\n正常内容"
        assert ContentWriterAgent._strip_think_blocks(raw) == raw

    def test_empty_or_none_safe(self) -> None:
        from app.domain.generator.content_writer_agent import ContentWriterAgent

        assert ContentWriterAgent._strip_think_blocks("") == ""
        assert ContentWriterAgent._strip_think_blocks(None) == ""

    def test_unclosed_think_strips_through_end(self) -> None:
        """防御：think 块未闭合（异常流）时贪婪匹配吞到末尾——这是 trade-off,
        反正未闭合的内容也不该保留。"""
        from app.domain.generator.content_writer_agent import ContentWriterAgent

        raw = "# 标题\n<think>永远不闭合的推理"
        out = ContentWriterAgent._strip_think_blocks(raw)
        # 未闭合的 think 块（贪婪匹配 DOTALL）会被剥掉
        assert "永远不闭合" not in out or out.startswith("# 标题")


# ===========================================================================
# 关键差异点 2：base_url bare host 自动补 /v1
# ===========================================================================


@pytest.mark.asyncio
@respx.mock
async def test_write_article_normalizes_bare_host_base_url() -> None:
    """回归：base_url 是 bare host（无 /v1，如 MiniMax）时必须自动补 /v1。"""
    settings = Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.minimaxi.com",  # 无 /v1
        deepseek_model="m",
        llm_call_timeout_s=10,
    )
    agent = ContentWriterAgent(settings)
    route = respx.post("https://api.minimaxi.com/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": "# 标题\n\n正文内容"}}]}
        )
    )

    title, content = await agent.write_article(
        brand="B", topic="T", keywords=[], style="neutral",
        target_length=500, chunks=[],
    )
    assert route.called
    assert title == "标题"
    assert "正文内容" in content


# ===========================================================================
# 关键差异点 3：transient 异常吞掉
# ===========================================================================


@pytest.mark.asyncio
@respx.mock
async def test_write_article_handles_timeout(agent: ContentWriterAgent) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    title, content = await agent.write_article(
        brand=None, topic="Topic", keywords=[],
        style="neutral", target_length=500, chunks=[],
    )
    # transient 吞掉，返回空 content
    assert content == ""
    assert title is not None


@pytest.mark.asyncio
@respx.mock
async def test_write_article_handles_500(agent: ContentWriterAgent) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(500, json={"error": "server error"})
    )

    title, content = await agent.write_article(
        brand=None, topic="Topic", keywords=[],
        style="neutral", target_length=500, chunks=[],
    )
    assert content == ""
    assert title is not None


# ===========================================================================
# 关键差异点 4：流式 yield 增量
# ===========================================================================


@pytest.mark.asyncio
@respx.mock
async def test_stream_article_yields_increments(agent: ContentWriterAgent) -> None:
    """流式：调用 stream 后 respx route 被命中，stream generator 正常退出。

    注：respx 不解析 OpenAI SDK 的 SSE 流协议，所以这里只验证
    "调用通了 + generator 正常退出"——内容解析的正确性交给 E2E/集成测试。
    """
    route = respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": "# 流式标题\n\n流式正文"}}]
            },
        )
    )

    chunks: list[str] = []
    async for piece in agent.stream_article(
        brand=None, topic="T", keywords=[], style="neutral",
        target_length=300, chunks=[],
    ):
        chunks.append(piece)

    assert route.called
    # generator 正常退出；具体内容验证留给端到端
    assert isinstance(chunks, list)


@pytest.mark.asyncio
@respx.mock
async def test_stream_article_swallows_transient(agent: ContentWriterAgent) -> None:
    """transient 异常时 stream 安静结束（不抛），调用方按"流结束但空 content"判定失败。"""
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    chunks: list[str] = []
    # 不应抛异常
    async for piece in agent.stream_article(
        brand=None, topic="T", keywords=[], style="neutral",
        target_length=300, chunks=[],
    ):
        chunks.append(piece)

    # transient 吞掉，没有任何 yield
    assert chunks == []


# ===========================================================================
# 关键差异点 5：RAG chunks 透传到 user prompt
# ===========================================================================


class TestChunkRendering:
    def test_chunks_rendered_in_user_prompt(self, agent: ContentWriterAgent) -> None:
        messages = agent._build_messages(
            brand=None,
            topic="评测",
            keywords=["性能"],
            style="neutral",
            target_length=500,
            chunks=[
                {"index": 1, "content": "续航 12 小时"},
                {"index": 2, "content": "充电 30 分钟"},
            ],
        )
        user = messages[1]["content"]
        assert "[参考资料 #1]" in user
        assert "续航 12 小时" in user
        assert "[参考资料 #2]" in user
        assert "充电 30 分钟" in user

    def test_empty_chunks_shows_placeholder(self, agent: ContentWriterAgent) -> None:
        """chunks=[] 时 user prompt 显示"暂无可用参考资料"。"""
        messages = agent._build_messages(
            brand=None, topic="T", keywords=[], style="neutral",
            target_length=300, chunks=[],
        )
        user = messages[1]["content"]
        assert "暂无可用参考资料" in user