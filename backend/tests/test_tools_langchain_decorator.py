# backend/tests/test_tools_langchain_decorator.py
from app.domain.agent.tools import LANGCHAIN_TOOLS, TOOLS


def test_langchain_tools_count_matches_schema():
    assert len(LANGCHAIN_TOOLS) == 5


def test_langchain_tools_cover_all_schema_names():
    schema_names = {t["function"]["name"] for t in TOOLS}
    decorator_names = {t.name for t in LANGCHAIN_TOOLS}
    assert schema_names == decorator_names


def test_langchain_tools_are_langchain_basetool():
    from langchain_core.tools import BaseTool
    for t in LANGCHAIN_TOOLS:
        assert isinstance(t, BaseTool)
