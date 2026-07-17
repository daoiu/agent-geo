"""③ 多模态摄取配置项测试。"""
from __future__ import annotations

from app.core.config import Settings


def test_multimodal_defaults() -> None:
    s = Settings()
    assert s.multimodal_enabled is True
    assert s.ocr_languages == ["ch_sim", "en"]
    assert s.ocr_gpu is False
    assert s.vision_max_tokens == 256
    assert s.vision_api_key == ""  # 缺省回退现有 provider