"""③ 图片 → 文本:EasyOCR 文字 + VLM 语义描述,合并输出。

降级链:
- base64 非法 → [图片：<alt>]
- OCR 可用 + 有文字 → [图片文字：...]
- VLM 可用 + 有描述 → [图片描述：...]
- 两者皆空 → [图片：<alt>]
任一步异常均软失败,不向调用方抛。
"""
from __future__ import annotations

import base64

import structlog

from app.core.config import get_settings
from app.services.multimodal.ocr_service import get_ocr_service

logger = structlog.get_logger()

_DESCRIBE_PROMPT = (
    "请用中文简要描述这张图片的语义内容,包括:"
    "架构/流程关系、数据趋势、界面逻辑等非文字信息。"
    "如果图片主要是文字截图,只需输出'文字型图片'。控制在 150 字以内。"
)


def _vlm_describe(image_b64: str, mime_type: str) -> str:
    """Vision API 语义描述。VISION_* 缺省回退 OPENAI_* / OPENAI_BASE_URL / OPENAI_MODEL。

    无 key / 异常 → 返回空串。
    """
    s = get_settings()
    import os

    api_key = s.vision_api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return ""
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=(s.vision_api_base or os.environ.get("OPENAI_BASE_URL") or None),
        )
        resp = client.chat.completions.create(
            model=(s.vision_model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _DESCRIBE_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            }],
            max_tokens=s.vision_max_tokens,
            temperature=0.1,
        )
        desc = (resp.choices[0].message.content or "").strip()
        return "" if desc == "文字型图片" else desc
    except Exception as exc:  # noqa: BLE001
        logger.warning("vlm_describe_failed", error=str(exc)[:120])
        return ""


def describe_image(image_b64: str, mime_type: str, alt_text: str = "") -> str:
    """合并 OCR 文字 + VLM 描述。失败退到 [图片：<alt>] 占位。"""
    try:
        base64.b64decode(image_b64, validate=True)
    except Exception:  # noqa: BLE001
        return f"[图片：{alt_text}]" if alt_text else "[图片]"

    parts: list[str] = []
    ocr = get_ocr_service()
    if ocr is not None:
        try:
            img_bytes = base64.b64decode(image_b64)
            ocr_text = ocr.extract_text(img_bytes)
            if ocr_text.strip():
                parts.append(f"[图片文字：{ocr_text.strip()}]")
        except Exception as exc:  # noqa: BLE001
            logger.warning("ocr_in_describe_failed", error=str(exc))

    vlm_desc = _vlm_describe(image_b64, mime_type)
    if vlm_desc:
        parts.append(f"[图片描述：{vlm_desc}]")

    if parts:
        return "\n".join(parts)
    return f"[图片：{alt_text}]" if alt_text else "[图片]"