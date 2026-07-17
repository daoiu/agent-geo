"""③ EasyOCR 封装测试。"""
from __future__ import annotations

import io

from PIL import Image

from app.services.multimodal.ocr_service import OCRService


def test_extract_dedup_and_join() -> None:
    svc = OCRService.__new__(OCRService)  # 跳过 __init__(不加载真模型)
    class _Reader:
        def readtext(self, img_np, detail=0):
            return ["行A", "行A", "行B"]

    svc._reader = _Reader()
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "PNG")
    assert svc.extract_text(buf.getvalue()) == "行A\n行B"


def test_extract_soft_fail_returns_empty() -> None:
    svc = OCRService.__new__(OCRService)
    class _Reader:
        def readtext(self, *a, **k):
            raise RuntimeError("boom")

    svc._reader = _Reader()
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "PNG")
    assert svc.extract_text(buf.getvalue()) == ""