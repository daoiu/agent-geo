"""Tests for ToolExecutor (v0.4)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.agent.tool_executor import ToolExecutor


@pytest.fixture
def executor() -> ToolExecutor:
    return ToolExecutor(session_id="test-session")


class TestDispatch:
    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self, executor: ToolExecutor) -> None:
        """Unknown tool name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await executor.execute("unknown_tool", {})

    @pytest.mark.asyncio
    async def test_validates_args_before_dispatch(self, executor: ToolExecutor) -> None:
        """Invalid args raise ValidationError before calling the inner method."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            await executor.execute("diagnose_brand", {"brand_name": "X"})  # missing others

    @pytest.mark.asyncio
    async def test_dispatches_to_diagnose(self, executor: ToolExecutor) -> None:
        """diagnose_brand calls _execute_diagnose_brand."""
        with patch.object(
            executor,
            "_execute_diagnose_brand",
            new=AsyncMock(return_value={"x": 1}),
        ) as mock_fn:
            result = await executor.execute(
                "diagnose_brand",
                {
                    "brand_name": "X",
                    "industry": "Y",
                    "official_url": "https://example.com",
                },
            )
            mock_fn.assert_called_once()
            assert result == {"x": 1}

    @pytest.mark.asyncio
    async def test_dispatches_to_search(self, executor: ToolExecutor) -> None:
        """search_knowledge calls _execute_search_knowledge."""
        with patch.object(
            executor,
            "_execute_search_knowledge",
            new=AsyncMock(return_value={"y": 2}),
        ) as mock_fn:
            result = await executor.execute(
                "search_knowledge",
                {"kb_id": "kb1", "query": "X"},
            )
            mock_fn.assert_called_once()
            assert result == {"y": 2}

    @pytest.mark.asyncio
    async def test_dispatches_to_generate(self, executor: ToolExecutor) -> None:
        """generate_article calls _execute_generate_article."""
        with patch.object(
            executor,
            "_execute_generate_article",
            new=AsyncMock(return_value={"z": 3}),
        ) as mock_fn:
            result = await executor.execute(
                "generate_article",
                {
                    "kb_id": "kb1",
                    "brand": "X",
                    "topic": "足够长的主题",
                    "keywords": ["k"],
                },
            )
            mock_fn.assert_called_once()
            assert result == {"z": 3}

    @pytest.mark.asyncio
    async def test_session_id_stored(self) -> None:
        """session_id is stored on the executor."""
        ex = ToolExecutor(session_id="my-session")
        assert ex.session_id == "my-session"