"""③ parse_pdf 注入 page.images OCR+VLM 测试。"""
from __future__ import annotations

import app.domain.knowledge.parser as P


def test_pdf_merges_image_description(monkeypatch, tmp_path) -> None:
    class _Img:
        data = b"\x89PNG..."
        image_type = "/png"

    class _Page:
        images = [_Img()]

        def extract_text(self):
            return "正文内容"

    class _Reader:
        pages = [_Page()]

    monkeypatch.setattr(P, "PdfReader", lambda path: _Reader())
    monkeypatch.setattr(P, "describe_image", lambda b64, mime, alt: "[图片描述：柱状图]")

    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF-1.4")
    out = P.parse_pdf(str(f))
    assert "正文内容" in out
    assert "[图片描述：柱状图]" in out


def test_pdf_no_images_unchanged(monkeypatch, tmp_path) -> None:
    class _Page:
        images = []

        def extract_text(self):
            return "纯文本页"

    class _Reader:
        pages = [_Page()]

    monkeypatch.setattr(P, "PdfReader", lambda path: _Reader())
    f = tmp_path / "y.pdf"
    f.write_bytes(b"%PDF-1.4")
    assert P.parse_pdf(str(f)).strip() == "纯文本页"