"""Tests for document parsers (TXT and MD covered initially)."""
import pytest

from app.domain.knowledge.parser import (
    DocumentParseError,
    parse_md,
    parse_txt,
)
from tests.conftest import PROJECT_ROOT


class TestTxtParser:
    def test_parses_plain_text(self) -> None:
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "sample.txt"
        text = parse_txt(str(fixture))
        assert "第一段" in text
        assert "第二段" in text

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(DocumentParseError):
            parse_txt(str(tmp_path / "nonexistent.txt"))


class TestMdParser:
    def test_parses_markdown_as_text(self) -> None:
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "sample.md"
        text = parse_md(str(fixture))
        assert "标题" in text
        assert "子标题" in text
