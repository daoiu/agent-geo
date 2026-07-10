"""Document parsers: extract plain text from PDF/Word/MD/TXT files.

TXT and MD parsers live in this file. PDF and DOCX are added in subsequent tasks.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.exceptions import DocumentParseError


def _read_text_file(path: str) -> str:
    """Read a UTF-8 text file. Raises DocumentParseError on failure."""
    p = Path(path)
    if not p.exists():
        raise DocumentParseError(
            doc_id=path, file_path=path, reason="file not found"
        )
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fall back to GBK (common for Chinese Windows files)
        try:
            return p.read_text(encoding="gbk")
        except Exception as e:  # noqa: BLE001
            raise DocumentParseError(
                doc_id=path, file_path=path, reason=f"encoding error: {e}"
            ) from e
    except Exception as e:  # noqa: BLE001
        raise DocumentParseError(
            doc_id=path, file_path=path, reason=str(e)
        ) from e


def parse_txt(path: str) -> str:
    """Parse a plain text file."""
    return _read_text_file(path)


def parse_md(path: str) -> str:
    """Parse a Markdown file. We treat it as text — Markdown syntax is preserved
    so downstream consumers (LLM prompts) can see structure.
    """
    return _read_text_file(path)
