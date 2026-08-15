"""Tests for the prompt builder."""
from app.domain.generator.prompt_builder import build


class TestPromptBuilder:
    def test_includes_brand(self) -> None:
        prompt = build(
            brand="小米", topic="手机", keywords=["性能"],
            style="professional", target_length=1500,
            chunks=[],
        )
        assert "小米" in prompt

    def test_includes_topic(self) -> None:
        prompt = build(
            brand=None, topic="国产手机推荐", keywords=[],
            style="neutral", target_length=1000,
            chunks=[],
        )
        assert "国产手机推荐" in prompt

    def test_includes_keywords(self) -> None:
        prompt = build(
            brand=None, topic="主题", keywords=["关键词A", "关键词B"],
            style="neutral", target_length=1000,
            chunks=[],
        )
        assert "关键词A" in prompt
        assert "关键词B" in prompt

    def test_includes_chunks(self) -> None:
        prompt = build(
            brand=None, topic="主题", keywords=[],
            style="neutral", target_length=1000,
            chunks=[{"index": 1, "content": "参考资料内容X"}],
        )
        assert "参考资料内容X" in prompt

    def test_empty_chunks_marks_no_reference(self) -> None:
        prompt = build(
            brand=None, topic="主题", keywords=[],
            style="neutral", target_length=1000,
            chunks=[],
        )
        assert "无参考资料" in prompt or "知识库暂无可用" in prompt

    def test_explicitly_forbids_fabrication(self) -> None:
        """Prompt must include the 'do not fabricate' instruction."""
        prompt = build(
            brand=None, topic="主题", keywords=[],
            style="neutral", target_length=1000,
            chunks=[],
        )
        assert "不得编造" in prompt or "不得虚构" in prompt
