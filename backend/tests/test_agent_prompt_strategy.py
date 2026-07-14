"""Tests for AGENT_SYSTEM_PROMPT strategy section (v0.6 P1.4)."""
from app.core.config import get_settings
from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT


def test_prompt_mentions_list_knowledge_bases() -> None:
    """Prompt 必须告诉 LLM 优先调 list_knowledge_bases 探索可用 KB."""
    assert "list_knowledge_bases" in AGENT_SYSTEM_PROMPT


def test_prompt_mentions_create_generation_task() -> None:
    """Prompt 必须告诉 LLM 多篇生成走 create_generation_task 而非循环."""
    assert "create_generation_task" in AGENT_SYSTEM_PROMPT


def test_prompt_mandates_source_attribution() -> None:
    """Prompt 要求 chunk 引用时附 kb_name + doc_filename（溯源）."""
    assert "kb_name" in AGENT_SYSTEM_PROMPT
    assert "doc_filename" in AGENT_SYSTEM_PROMPT


def test_max_react_iterations_is_seven() -> None:
    """Settings.max_react_iterations 默认 7（v0.6 P1.4: 5 → 7，给 list → search → create_task 三步留余量）。"""
    assert get_settings().max_react_iterations == 7
