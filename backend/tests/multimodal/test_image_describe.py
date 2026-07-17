"""③ 图片描述测试:OCR + VLM 合并 + 软失败。"""
from __future__ import annotations

import app.services.multimodal.image_describe as mod
from app.services.multimodal.image_describe import describe_image


def test_merge_ocr_and_vlm(monkeypatch) -> None:
    class _OCR:
        def extract_text(self, b):
            return "图中文字X"

    monkeypatch.setattr(mod, "get_ocr_service", lambda: _OCR())
    monkeypatch.setattr(mod, "_vlm_describe", lambda b64, mime: "一张架构图")
    out = describe_image("Zm9v", "image/png", "alt")
    assert "[图片文字：图中文字X]" in out
    assert "[图片描述：一张架构图]" in out


def test_only_ocr_when_vlm_empty(monkeypatch) -> None:
    class _OCR:
        def extract_text(self, b):
            return "只有文字"

    monkeypatch.setattr(mod, "get_ocr_service", lambda: _OCR())
    monkeypatch.setattr(mod, "_vlm_describe", lambda b64, mime: "")
    out = describe_image("Zm9v", "image/png", "alt")
    assert out == "[图片文字：只有文字]"


def test_both_empty_falls_back_to_alt(monkeypatch) -> None:
    monkeypatch.setattr(mod, "get_ocr_service", lambda: None)
    monkeypatch.setattr(mod, "_vlm_describe", lambda b64, mime: "")
    assert describe_image("Zm9v", "image/png", "封面") == "[图片：封面]"


def test_bad_b64_returns_alt(monkeypatch) -> None:
    monkeypatch.setattr(mod, "get_ocr_service", lambda: None)
    monkeypatch.setattr(mod, "_vlm_describe", lambda b64, mime: "")
    assert describe_image("!!!非base64!!!", "image/png", "x") == "[图片：x]"