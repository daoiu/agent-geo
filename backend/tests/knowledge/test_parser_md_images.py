"""③ parse_md 注入 base64 data-uri 图片替换测试。"""
from __future__ import annotations

import app.domain.knowledge.parser as P


def test_md_replaces_base64_image(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(P, "describe_image", lambda b64, mime, alt: "[图片描述：示意图]")
    md = "前文\n![封面](data:image/png;base64,Zm9v)\n后文"
    f = tmp_path / "a.md"
    f.write_text(md, encoding="utf-8")
    out = P.parse_md(str(f))
    assert "前文" in out and "后文" in out
    assert "[图片描述：示意图]" in out
    assert "base64" not in out


def test_md_no_image_unchanged(tmp_path) -> None:
    f = tmp_path / "b.md"
    f.write_text("# 标题\n正文", encoding="utf-8")
    assert P.parse_md(str(f)) == "# 标题\n正文"