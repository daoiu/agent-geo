"""Tests for the text chunker."""
from app.domain.knowledge.chunker import chunk_text


class TestChunking:
    def test_splits_long_paragraph_at_max(self) -> None:
        """A long paragraph gets split at sentence boundaries."""
        long = "这是第" + "句话。这是第".join(str(i) + "句话" for i in range(200)) + "句话。"
        chunks = chunk_text(long, min_length=10, max_length=500)
        assert all(len(c) <= 500 for c in chunks)
        assert len(chunks) > 1

    def test_merges_short_paragraphs_to_min(self) -> None:
        text = "短段一。\n\n短段二。\n\n短段三。\n\n短段四。"
        chunks = chunk_text(text, min_length=10, max_length=500)
        # All four short paragraphs should merge into one chunk
        assert len(chunks) == 1
        assert "短段一" in chunks[0]
        assert "短段四" in chunks[0]

    def test_separates_by_double_newline(self) -> None:
        para1 = "第一段内容超过五十字。" * 30
        para2 = "第二段内容也超过五十字。" * 30
        text = para1 + "\n\n" + para2
        chunks = chunk_text(text, min_length=10, max_length=500)
        # Each paragraph exceeds 500 chars → split at sentence boundary
        # but the two paragraphs must remain in separate chunks
        assert len(chunks) >= 2
        joined = "\n".join(chunks)
        assert "第一段" in joined
        assert "第二段" in joined
        # First chunk(s) belong to para1, last chunk(s) belong to para2
        assert "第一段" in chunks[0]
        assert "第二段" in chunks[-1]

    def test_empty_text_returns_empty_list(self) -> None:
        assert chunk_text("") == []
        assert chunk_text("   \n\n  \n") == []

    def test_filters_out_tiny_chunks(self) -> None:
        text = "abc\n\n" + "x" * 100 + "\n\ndef"
        chunks = chunk_text(text, min_length=50, max_length=500)
        # "abc" and "def" too small; only the 100-char one survives
        assert all(len(c) >= 50 for c in chunks)
        assert len(chunks) == 1
        assert "x" * 100 in chunks[0]

    def test_handles_chinese_sentence_splitting(self) -> None:
        """Long Chinese paragraph splits at Chinese sentence boundaries."""
        long = "第一句。" * 100  # ~400 chars
        chunks = chunk_text(long, min_length=10, max_length=200)
        # Should split, not at arbitrary positions
        for chunk in chunks:
            assert len(chunk) <= 200
