"""Text chunker: splits long text into 50-500 char segments at sentence boundaries."""
from __future__ import annotations

import re

# Chinese + English sentence terminators
_SENTENCE_END = re.compile(r"([。！？.!?\n])")


def _split_long_paragraph(paragraph: str, max_length: int) -> list[str]:
    """Split a paragraph longer than max_length at sentence boundaries."""
    if len(paragraph) <= max_length:
        return [paragraph]

    # Split into sentences (keeping the terminator)
    pieces = _SENTENCE_END.split(paragraph)
    # Re-join: split() alternates text/separator, e.g. ["a", "。", "b", "。", ...]
    sentences: list[str] = []
    for i in range(0, len(pieces) - 1, 2):
        text = pieces[i]
        sep = pieces[i + 1] if i + 1 < len(pieces) else ""
        if text or sep:
            sentences.append(text + sep)

    # Pack sentences into chunks ≤ max_length
    chunks: list[str] = []
    buffer = ""
    for sentence in sentences:
        if len(buffer) + len(sentence) <= max_length:
            buffer += sentence
        else:
            if buffer:
                chunks.append(buffer)
            if len(sentence) > max_length:
                # Single sentence longer than max — hard cut
                chunks.append(sentence[:max_length])
                buffer = sentence[max_length:]
            else:
                buffer = sentence
    if buffer:
        chunks.append(buffer)
    return [c for c in chunks if c.strip()]


def chunk_text(
    text: str, min_length: int = 50, max_length: int = 500
) -> list[str]:
    """Split text into chunks of 50-500 characters.

    Algorithm:
    1. Split by double newlines (paragraphs)
    2. Each paragraph > max_length → split at sentence boundaries
    3. Merge consecutive short paragraphs until ≥ min_length
    4. Drop final chunks < min_length
    """
    if not text or not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Phase 1: split long paragraphs
    pieces: list[str] = []
    for p in paragraphs:
        pieces.extend(_split_long_paragraph(p, max_length))

    # Phase 2: merge short consecutive pieces
    chunks: list[str] = []
    buffer = ""
    for piece in pieces:
        if len(buffer) + len(piece) + 2 <= max_length:
            buffer = (buffer + "\n\n" + piece) if buffer else piece
        else:
            if buffer:
                chunks.append(buffer)
            buffer = piece
    if buffer:
        chunks.append(buffer)

    # Phase 3: filter by min_length
    return [c.strip() for c in chunks if len(c.strip()) >= min_length]
