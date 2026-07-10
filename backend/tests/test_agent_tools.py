"""Tests for agent tool schemas and validation (v0.4)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.agent.tools import (
    TOOLS,
    TOOL_NAMES,
    DiagnoseBrandArgs,
    GenerateArticleArgs,
    SearchKnowledgeArgs,
    ToolName,
    get_tool_schema,
    validate_tool_args,
)


class TestToolRegistry:
    def test_three_tools_registered(self) -> None:
        """Exactly 3 tools are exposed to the LLM."""
        assert len(TOOLS) == 3

    def test_tool_names_match_enum(self) -> None:
        """TOOL_NAMES equals the three tool names."""
        assert TOOL_NAMES == {"diagnose_brand", "search_knowledge", "generate_article"}

    def test_each_tool_has_function_type(self) -> None:
        """Each tool entry is OpenAI-compatible function-call type."""
        for t in TOOLS:
            assert t["type"] == "function"
            assert "function" in t
            assert "name" in t["function"]
            assert "description" in t["function"]
            assert "parameters" in t["function"]

    def test_get_tool_schema_returns_correct_tool(self) -> None:
        """get_tool_schema('diagnose_brand') returns the diagnose_brand schema."""
        schema = get_tool_schema("diagnose_brand")
        assert schema["name"] == "diagnose_brand"
        assert "description" in schema
        assert "parameters" in schema

    def test_get_tool_schema_unknown_raises(self) -> None:
        """Unknown tool name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            get_tool_schema("does_not_exist")


class TestValidateDiagnoseArgs:
    def test_valid_args(self) -> None:
        """All three required fields accepted."""
        args = validate_tool_args(
            "diagnose_brand",
            {
                "brand_name": "小米",
                "industry": "手机",
                "official_url": "https://www.mi.com",
            },
        )
        assert isinstance(args, DiagnoseBrandArgs)
        assert args.brand_name == "小米"
        assert args.industry == "手机"
        assert str(args.official_url) == "https://www.mi.com/"

    def test_missing_brand_name(self) -> None:
        """Missing brand_name raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "diagnose_brand",
                {"industry": "手机", "official_url": "https://www.mi.com"},
            )

    def test_missing_industry(self) -> None:
        """Missing industry raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "diagnose_brand",
                {"brand_name": "小米", "official_url": "https://www.mi.com"},
            )

    def test_missing_url(self) -> None:
        """Missing official_url raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "diagnose_brand",
                {"brand_name": "小米", "industry": "手机"},
            )

    def test_invalid_url(self) -> None:
        """Non-URL official_url raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "diagnose_brand",
                {
                    "brand_name": "X",
                    "industry": "Y",
                    "official_url": "not-a-url",
                },
            )


class TestValidateSearchArgs:
    def test_valid_args(self) -> None:
        """kb_id + query accepted, limit defaults to 5."""
        args = validate_tool_args(
            "search_knowledge",
            {"kb_id": "kb-123", "query": "产品功能"},
        )
        assert isinstance(args, SearchKnowledgeArgs)
        assert args.kb_id == "kb-123"
        assert args.query == "产品功能"
        assert args.limit == 5  # default

    def test_custom_limit(self) -> None:
        """Custom limit within bounds accepted."""
        args = validate_tool_args(
            "search_knowledge",
            {"kb_id": "kb-123", "query": "X", "limit": 10},
        )
        assert args.limit == 10

    def test_limit_too_high(self) -> None:
        """limit > 10 raises ValidationError (matches schema description)."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "search_knowledge",
                {"kb_id": "kb-123", "query": "X", "limit": 100},
            )

    def test_limit_zero(self) -> None:
        """limit < 1 raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "search_knowledge",
                {"kb_id": "kb-123", "query": "X", "limit": 0},
            )

    def test_missing_query(self) -> None:
        """Missing query raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args("search_knowledge", {"kb_id": "kb-123"})


class TestValidateGenerateArgs:
    def test_valid_args(self) -> None:
        """All required fields accepted, defaults applied."""
        args = validate_tool_args(
            "generate_article",
            {
                "kb_id": "kb-123",
                "brand": "小米",
                "topic": "小米 14 Pro 产品评测",  # 11 字符 ≥ 5
                "keywords": ["性能", "拍照"],
            },
        )
        assert isinstance(args, GenerateArticleArgs)
        assert args.brand == "小米"
        assert args.style == "neutral"  # default
        assert args.target_length == 1500  # default

    def test_short_topic(self) -> None:
        """topic shorter than 5 chars raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "generate_article",
                {
                    "kb_id": "kb",
                    "brand": "X",
                    "topic": "短",
                    "keywords": ["k"],
                },
            )

    def test_empty_keywords(self) -> None:
        """Empty keywords list raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "generate_article",
                {
                    "kb_id": "kb",
                    "brand": "X",
                    "topic": "足够长的主题",
                    "keywords": [],
                },
            )

    def test_custom_style(self) -> None:
        """style can be one of the three enum values."""
        args = validate_tool_args(
            "generate_article",
            {
                "kb_id": "kb",
                "brand": "X",
                "topic": "足够长的主题",
                "keywords": ["k"],
                "style": "professional",
            },
        )
        assert args.style == "professional"

    def test_invalid_style(self) -> None:
        """Invalid style raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_tool_args(
                "generate_article",
                {
                    "kb_id": "kb",
                    "brand": "X",
                    "topic": "足够长的主题",
                    "keywords": ["k"],
                    "style": "marketing",
                },
            )


class TestValidateUnknownTool:
    def test_unknown_tool_raises_value_error(self) -> None:
        """validate_tool_args with unknown tool raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            validate_tool_args("unknown_tool", {})


class TestToolNameEnum:
    def test_enum_values(self) -> None:
        """ToolName enum has all three tools."""
        assert ToolName.DIAGNOSE_BRAND.value == "diagnose_brand"
        assert ToolName.SEARCH_KNOWLEDGE.value == "search_knowledge"
        assert ToolName.GENERATE_ARTICLE.value == "generate_article"