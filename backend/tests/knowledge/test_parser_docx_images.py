"""③ parse_docx 注入 rels/blip 图片描述测试。"""
from __future__ import annotations

import app.domain.knowledge.parser as P
from app.domain.knowledge.parser import _describe_docx_images


def test_docx_appends_image_desc(monkeypatch) -> None:
    class _Part:
        blob = b"\x89PNG"
        content_type = "image/png"

    class _Rel:
        reltype = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
        target_part = _Part()

    class _DocPart:
        rels = {"rId1": _Rel()}

    class _Doc:
        part = _DocPart()

    monkeypatch.setattr(P, "describe_image", lambda b64, mime, alt: "[图片描述：流程图]")
    descs = _describe_docx_images(_Doc())
    assert descs == ["[图片描述：流程图]"]