"""③ EasyOCR 封装:懒加载模型,从图片字节提取文字。软失败返回空。

单例由 get_ocr_service() 提供;模型加载在首次 extract_text() 触发(懒)。
任何内部异常(模型缺 / 加载失败 / 推理失败)→ 返回空串,不向调用方抛。
"""
from __future__ import annotations

import io

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
_INSTANCE: "OCRService | None" = None
_INIT_DONE = False


class OCRService:
    """EasyOCR 懒加载封装。"""

    def __init__(self, languages: list[str] | None = None, gpu: bool = False) -> None:
        self._languages = languages or ["ch_sim", "en"]
        self._gpu = gpu
        self._reader = None

    @property
    def reader(self):
        if self._reader is None:
            import easyocr  # noqa: PLC0415

            logger.info("easyocr_loading", langs=self._languages, gpu=self._gpu)
            self._reader = easyocr.Reader(self._languages, gpu=self._gpu)
        return self._reader

    def extract_text(self, image_bytes: bytes) -> str:
        """从图片字节 OCR 文字,行内去重后 '\n' 拼接。失败返回空串。"""
        try:
            import numpy as np  # noqa: PLC0415
            from PIL import Image  # noqa: PLC0415

            img = Image.open(io.BytesIO(image_bytes))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            results = self.reader.readtext(np.array(img), detail=0)
            seen: set[str] = set()
            unique: list[str] = []
            for text in results:
                t = text.strip()
                if t and t not in seen:
                    seen.add(t)
                    unique.append(t)
            return "\n".join(unique)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ocr_extract_failed", error=str(exc))
            return ""


def get_ocr_service() -> "OCRService | None":
    """单例。multimodal_enabled=False → None。模型加载在首次 extract 时触发(懒)。"""
    global _INSTANCE, _INIT_DONE
    if _INIT_DONE:
        return _INSTANCE
    _INIT_DONE = True
    s = get_settings()
    if not s.multimodal_enabled:
        _INSTANCE = None
    else:
        _INSTANCE = OCRService(languages=list(s.ocr_languages), gpu=s.ocr_gpu)
    return _INSTANCE