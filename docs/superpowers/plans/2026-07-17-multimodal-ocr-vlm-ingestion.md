# ③ OCR+VLM 多模态摄取实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 PDF/DOCX/MD 抽出内嵌图片,经 EasyOCR(本地)+ VLM(provider Vision API)转为文本描述,合并回文档正文再进现有分块/向量化,解决图片信息丢失。

**Architecture:** 新增 `app/services/multimodal/`(ocr_service / image_describe),把 `describe_image` 注入现有 `app/domain/knowledge/parser.py` 的 `parse_pdf`/`parse_docx`/`parse_md`。全程软降级:模型缺 / 无 key / 单图失败均不影响文本抽取。

**Tech Stack:** EasyOCR(本地,torch 已装)· OpenAI 兼容 Vision API · pypdf(`page.images`)· python-docx(`doc.part.rels` + `a:blip`)· pytest。

## Global Constraints

- 语言:对话 / docstring 用简体中文。
- **前置准备(实施前)**:`pip install easyocr`(GEO2 venv 已有 torch);有网环境补全 `~/.EasyOCR/model/` 的 `.pth`(现仅 temp.zip)。补全前 OCR 路软降级。
- 沿用 GEO2 **函数式 parser + `@_handle_parse_errors`**,注入而非重写。
- 软降级:OCR 失败 → 返回空;VLM 无 key / 不支持 image_url → 返回空;两路空 → 退 `[图片：alt]`;**无图文档行为完全不变**。
- 解析函数是**同步**的 → OCR/VLM 调用同步(EasyOCR 同步、OpenAI 同步 client)。
- 测试位置:`backend/tests/multimodal/` 与 `backend/tests/knowledge/`(pyproject `testpaths=["tests"]`、工作目录 `backend/`)。

**关键既有符号:**
- `app/domain/knowledge/parser.py`:`parse_pdf`(L71)、`parse_docx`(L94)、`parse_md`(L65)、`_handle_parse_errors`(L26)、`_read_text_file`(L50)
- `app.core.config.get_settings()`
- pypdf `PdfReader(path).pages[i].extract_text()` / `.images[j].data` / `.image_type`

---

### Task 1: 配置项

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/multimodal/test_config.py`

**Interfaces:**
- Produces:`multimodal_enabled` / `ocr_languages` / `ocr_gpu` / `vision_api_key` / `vision_api_base` / `vision_model` / `vision_max_tokens`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/multimodal/test_config.py
from app.core.config import get_settings


def test_multimodal_defaults():
    s = get_settings()
    assert s.multimodal_enabled is True
    assert s.ocr_languages == ["ch_sim", "en"]
    assert s.ocr_gpu is False
    assert s.vision_max_tokens == 256
    assert s.vision_api_key == ""  # 缺省回退现有 provider
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/multimodal/test_config.py -v`
Expected: FAIL(AttributeError)

- [ ] **Step 3: 实现**

`config.py` 追加:
```python
    # ③ OCR+VLM 多模态
    multimodal_enabled: bool = True
    ocr_languages: list[str] = ["ch_sim", "en"]
    ocr_gpu: bool = False
    vision_api_key: str = ""
    vision_api_base: str = ""
    vision_model: str = ""
    vision_max_tokens: int = 256
```
`.env.example` 追加:
```
# ③ 多模态(Vision;缺省回退现有 provider)
VISION_API_KEY=
VISION_API_BASE=
VISION_MODEL=
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/multimodal/test_config.py -v` → PASS
```bash
git add backend/app/core/config.py .env.example backend/tests/multimodal/test_config.py
git commit -m "feat(multimodal): ③ 配置项"
```

---

### Task 2: EasyOCR 封装 `ocr_service.py`

**Files:**
- Create: `backend/app/services/multimodal/__init__.py`(空)
- Create: `backend/app/services/multimodal/ocr_service.py`
- Test: `backend/tests/multimodal/test_ocr_service.py`

**Interfaces:**
- Produces:
  - `class OCRService`:`extract_text(image_bytes: bytes) -> str`(去重拼接;任何异常返回空)
  - `get_ocr_service() -> OCRService | None`(`multimodal_enabled=False` 返回 None;单例)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/multimodal/test_ocr_service.py
from app.services.multimodal.ocr_service import OCRService


def test_extract_dedup_and_join(monkeypatch):
    svc = OCRService.__new__(OCRService)   # 跳过 __init__(不加载真模型)
    class _Reader:
        def readtext(self, img_np, detail=0):
            return ["行A", "行A", "行B"]
    svc._reader = _Reader()
    # 直接喂一张最小 PNG 字节(用 PIL 生成)
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (4, 4)).save(buf, "PNG")
    out = svc.extract_text(buf.getvalue())
    assert out == "行A\n行B"


def test_extract_soft_fail_returns_empty():
    svc = OCRService.__new__(OCRService)
    class _Reader:
        def readtext(self, *a, **k): raise RuntimeError("boom")
    svc._reader = _Reader()
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (4, 4)).save(buf, "PNG")
    assert svc.extract_text(buf.getvalue()) == ""
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/multimodal/test_ocr_service.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
# backend/app/services/multimodal/ocr_service.py
"""EasyOCR 封装:懒加载模型,从图片字节提取文字。软失败返回空。"""
from __future__ import annotations

import io

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
_INSTANCE: "OCRService | None" = None
_INIT_DONE = False


class OCRService:
    def __init__(self, languages: list[str] | None = None, gpu: bool = False) -> None:
        self._languages = languages or ["ch_sim", "en"]
        self._gpu = gpu
        self._reader = None

    @property
    def reader(self):
        if self._reader is None:
            import easyocr
            logger.info("easyocr_loading", langs=self._languages, gpu=self._gpu)
            self._reader = easyocr.Reader(self._languages, gpu=self._gpu)
        return self._reader

    def extract_text(self, image_bytes: bytes) -> str:
        try:
            import numpy as np
            from PIL import Image

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
```
建空 `__init__.py`。

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/multimodal/test_ocr_service.py -v` → PASS(2 passed)
```bash
git add backend/app/services/multimodal/__init__.py backend/app/services/multimodal/ocr_service.py backend/tests/multimodal/test_ocr_service.py
git commit -m "feat(multimodal): EasyOCR 封装 + 单例 + 软失败 + 2 用例"
```

---

### Task 3: 图片描述 `image_describe.py`(OCR + VLM 合并)

**Files:**
- Create: `backend/app/services/multimodal/image_describe.py`
- Test: `backend/tests/multimodal/test_image_describe.py`

**Interfaces:**
- Consumes: `get_ocr_service`(T2)、OpenAI 兼容 Vision client
- Produces:
  - `describe_image(image_b64: str, mime_type: str, alt_text: str = "") -> str`
  - `_vlm_describe(image_b64: str, mime_type: str) -> str`(无 key / 异常 → 空)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/multimodal/test_image_describe.py
import app.services.multimodal.image_describe as mod
from app.services.multimodal.image_describe import describe_image


def test_merge_ocr_and_vlm(monkeypatch):
    class _OCR:
        def extract_text(self, b): return "图中文字X"
    monkeypatch.setattr(mod, "get_ocr_service", lambda: _OCR())
    monkeypatch.setattr(mod, "_vlm_describe", lambda b64, mime: "一张架构图")
    out = describe_image("Zm9v", "image/png", "alt")
    assert "[图片文字：图中文字X]" in out
    assert "[图片描述：一张架构图]" in out


def test_only_ocr_when_vlm_empty(monkeypatch):
    class _OCR:
        def extract_text(self, b): return "只有文字"
    monkeypatch.setattr(mod, "get_ocr_service", lambda: _OCR())
    monkeypatch.setattr(mod, "_vlm_describe", lambda b64, mime: "")
    out = describe_image("Zm9v", "image/png", "alt")
    assert out == "[图片文字：只有文字]"


def test_both_empty_falls_back_to_alt(monkeypatch):
    monkeypatch.setattr(mod, "get_ocr_service", lambda: None)
    monkeypatch.setattr(mod, "_vlm_describe", lambda b64, mime: "")
    assert describe_image("Zm9v", "image/png", "封面") == "[图片：封面]"


def test_bad_b64_returns_alt(monkeypatch):
    monkeypatch.setattr(mod, "get_ocr_service", lambda: None)
    monkeypatch.setattr(mod, "_vlm_describe", lambda b64, mime: "")
    assert describe_image("!!!非base64!!!", "image/png", "x") == "[图片：x]"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/multimodal/test_image_describe.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
# backend/app/services/multimodal/image_describe.py
"""图片 → 文本:EasyOCR 文字 + VLM 语义描述,合并。均软失败。"""
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
    """Vision API 语义描述。VISION_* 缺省回退 OPENAI_*。失败返回空。"""
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
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
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
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/multimodal/test_image_describe.py -v` → PASS(4 passed)
```bash
git add backend/app/services/multimodal/image_describe.py backend/tests/multimodal/test_image_describe.py
git commit -m "feat(multimodal): 图片描述 OCR+VLM 合并 + 软失败退占位 + 4 用例"
```

---

### Task 4: 注入 `parse_pdf`(page.images)

**Files:**
- Modify: `backend/app/domain/knowledge/parser.py`
- Test: `backend/tests/knowledge/test_parser_pdf_images.py`

**Interfaces:**
- Consumes: `describe_image`(T3)
- Produces:`parse_pdf` 输出含每页图片的 `[图片文字/描述]`;无图 PDF 输出不变

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/knowledge/test_parser_pdf_images.py
import app.domain.knowledge.parser as P


def test_pdf_merges_image_description(monkeypatch, tmp_path):
    # mock PdfReader:一页含 text + 一张 image
    class _Img:
        data = b"\x89PNG..."
        image_type = "/png"
    class _Page:
        images = [_Img()]
        def extract_text(self): return "正文内容"
    class _Reader:
        pages = [_Page()]
    monkeypatch.setattr(P, "PdfReader", lambda path: _Reader())
    monkeypatch.setattr(P, "describe_image", lambda b64, mime, alt: "[图片描述：柱状图]")

    f = tmp_path / "x.pdf"; f.write_bytes(b"%PDF-1.4")
    out = P.parse_pdf(str(f))
    assert "正文内容" in out
    assert "[图片描述：柱状图]" in out


def test_pdf_no_images_unchanged(monkeypatch, tmp_path):
    class _Page:
        images = []
        def extract_text(self): return "纯文本页"
    class _Reader:
        pages = [_Page()]
    monkeypatch.setattr(P, "PdfReader", lambda path: _Reader())
    f = tmp_path / "y.pdf"; f.write_bytes(b"%PDF-1.4")
    assert P.parse_pdf(str(f)).strip() == "纯文本页"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/knowledge/test_parser_pdf_images.py -v`
Expected: FAIL(图片描述未拼入 / describe_image 不存在于 parser 命名空间)

- [ ] **Step 3: 实现**

`parser.py` 顶部加 `import base64` 与 `from app.services.multimodal.image_describe import describe_image`。改 `parse_pdf` 的 per-page 循环:
```python
    texts: list[str] = []
    for page_idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception as e:  # noqa: BLE001
            page_text = f"[page extraction failed: {e}]"
        image_descs: list[str] = []
        try:
            for img_idx, img in enumerate(getattr(page, "images", []) or []):
                try:
                    img_mime = img.image_type
                    img_mime = "image/" + img_mime[1:] if img_mime.startswith("/") else (
                        img_mime if img_mime.startswith("image/") else "image/" + img_mime)
                    b64 = base64.b64encode(img.data).decode("ascii")
                    desc = describe_image(b64, img_mime, f"PDF第{page_idx+1}页图{img_idx+1}")
                    if desc:
                        image_descs.append(desc)
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            pass
        merged = page_text + ("\n" + "\n".join(image_descs) if image_descs else "")
        if merged.strip():
            texts.append(merged)
    return "\n\n".join(texts)
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/knowledge/test_parser_pdf_images.py -v` → PASS(2 passed)
```bash
git add backend/app/domain/knowledge/parser.py backend/tests/knowledge/test_parser_pdf_images.py
git commit -m "feat(multimodal): parse_pdf 注入 page.images OCR+VLM + 2 用例"
```

---

### Task 5: 注入 `parse_docx`(rels / a:blip)

**Files:**
- Modify: `backend/app/domain/knowledge/parser.py`
- Test: `backend/tests/knowledge/test_parser_docx_images.py`

**Interfaces:**
- Consumes: `describe_image`
- Produces:`parse_docx` 输出含内嵌图片描述;无图 docx 输出不变

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/knowledge/test_parser_docx_images.py
import app.domain.knowledge.parser as P


def test_docx_appends_image_desc(monkeypatch):
    from app.domain.knowledge.parser import _describe_docx_images

    class _Part:
        blob = b"\x89PNG"
        content_type = "image/png"
    class _Rel:
        reltype = "http://.../image"
        target_part = _Part()
    class _DocPart:
        rels = {"rId1": _Rel()}
    class _Doc:
        part = _DocPart()
    monkeypatch.setattr(P, "describe_image", lambda b64, mime, alt: "[图片描述：流程图]")
    descs = _describe_docx_images(_Doc())
    assert descs == ["[图片描述：流程图]"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/knowledge/test_parser_docx_images.py -v`
Expected: FAIL(`_describe_docx_images` 不存在)

- [ ] **Step 3: 实现**

`parser.py` 新增 helper 并在 `parse_docx` 末尾追加图片描述:
```python
def _describe_docx_images(document) -> list[str]:
    """从 docx rels 抽出图片,OCR+VLM 描述。失败静默,返回描述列表。"""
    descs: list[str] = []
    try:
        rels = document.part.rels
    except Exception:  # noqa: BLE001
        return descs
    i = 0
    for _rid, rel in rels.items():
        if "image" not in getattr(rel, "reltype", ""):
            continue
        try:
            blob = rel.target_part.blob
            mime = rel.target_part.content_type or "image/png"
            i += 1
            b64 = base64.b64encode(blob).decode("ascii")
            desc = describe_image(b64, mime, f"DOCX图片{i}")
            if desc:
                descs.append(desc)
        except Exception:  # noqa: BLE001
            continue
    return descs
```
在 `parse_docx` 的 `return` 前:
```python
    parts.extend(_describe_docx_images(document))
    return "\n\n".join(parts)
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/knowledge/test_parser_docx_images.py -v` → PASS
```bash
git add backend/app/domain/knowledge/parser.py backend/tests/knowledge/test_parser_docx_images.py
git commit -m "feat(multimodal): parse_docx 注入 rels/blip 图片描述 + 用例"
```

---

### Task 6: 注入 `parse_md`(base64 data-uri)

**Files:**
- Modify: `backend/app/domain/knowledge/parser.py`
- Test: `backend/tests/knowledge/test_parser_md_images.py`

**Interfaces:**
- Consumes: `describe_image`
- Produces:`parse_md` 把 `![](data:image/..;base64,..)` 替换为描述;无图 md 不变

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/knowledge/test_parser_md_images.py
import app.domain.knowledge.parser as P


def test_md_replaces_base64_image(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "describe_image", lambda b64, mime, alt: "[图片描述：示意图]")
    md = "前文\n![封面](data:image/png;base64,Zm9v)\n后文"
    f = tmp_path / "a.md"; f.write_text(md, encoding="utf-8")
    out = P.parse_md(str(f))
    assert "前文" in out and "后文" in out
    assert "[图片描述：示意图]" in out
    assert "base64" not in out


def test_md_no_image_unchanged(tmp_path):
    f = tmp_path / "b.md"; f.write_text("# 标题\n正文", encoding="utf-8")
    assert P.parse_md(str(f)) == "# 标题\n正文"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/knowledge/test_parser_md_images.py -v`
Expected: FAIL(base64 图片未替换)

- [ ] **Step 3: 实现**

`parser.py` 加正则 + 替换,改 `parse_md`:
```python
import re
_IMG_DATA_URI_RE = re.compile(
    r"!\[([^\]]*)\]\(data:(image/[\w.+-]+);base64,([A-Za-z0-9+/=]+)\)"
)


def _replace_md_images(md_text: str) -> str:
    def _sub(m):
        alt, mime, b64 = m.group(1), m.group(2), m.group(3)
        try:
            return describe_image(b64, mime, alt)
        except Exception:  # noqa: BLE001
            return f"[图片：{alt}]" if alt else "[图片]"
    return _IMG_DATA_URI_RE.sub(_sub, md_text)
```
`parse_md` 改为:
```python
@_handle_parse_errors
def parse_md(path: str) -> str:
    return _replace_md_images(_read_text_file(path))
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/knowledge/test_parser_md_images.py -v` → PASS(2 passed)
```bash
git add backend/app/domain/knowledge/parser.py backend/tests/knowledge/test_parser_md_images.py
git commit -m "feat(multimodal): parse_md 注入 base64 图片替换 + 2 用例"
```

---

### Task 7: 依赖 + 前置说明 + 回归

**Files:**
- Modify: `backend/pyproject.toml`(加 `easyocr`)
- Modify: `README.md`(前置准备段)
- Test: 全量回归

- [ ] **Step 1: 加依赖 + 装**

`pyproject.toml` dependencies 加 `"easyocr>=1.7"`。
Run: `cd backend && pip install "easyocr>=1.7"`

- [ ] **Step 2: 补全模型(有网环境,一次性)**

```bash
cd backend && python -c "import easyocr; easyocr.Reader(['ch_sim','en'], gpu=False)"
```
Expected: 下载并解压 `~/.EasyOCR/model/` 的 `.pth`(craft_mlt_25k / zh_sim_g2 / english_g2)。

- [ ] **Step 3: README 前置准备段**

在 README 加一节:easyocr 安装 + 模型补全说明 + "未补全时 OCR 软降级、VLM 需 VISION_* 或回退 OPENAI_*"。

- [ ] **Step 4: 全量回归 + 提交**

Run: `cd backend && python -m pytest tests/multimodal/ tests/knowledge/ -v && python -m pytest tests/ -q`
Expected: 多模态 + parser 全绿,全量无回归。
```bash
git add backend/pyproject.toml README.md
git commit -m "chore(multimodal): easyocr 依赖 + 前置准备文档 + 回归"
```

---

## Self-Review

**Spec coverage:**
- 配置项 → T1 ✅
- EasyOCR 封装(懒加载 + 软失败)→ T2 ✅
- describe_image OCR+VLM 合并 + `_vlm_describe` → T3 ✅
- parse_pdf 注入(page.images)→ T4 ✅
- parse_docx 注入(rels/blip)→ T5 ✅
- parse_md 注入(base64 正则)→ T6 ✅
- 降级链(模型缺 / 无 key / 单图失败 / 无图不变)→ T2/T3 + 各 parser 的 no-image 回归用例 ✅
- 依赖 + 前置准备 + 回归 → T7 ✅
- 非目标(不改分块检索 / 无视频音频 / 不本地 VLM / 无 Unstructured)→ 未纳入 ✅

**Placeholder scan:** 无 TBD;每个代码步骤含完整代码。T7 Step 2 依赖有网补模型,已标注一次性前置。

**Type consistency:** `describe_image(image_b64, mime_type, alt_text)` T3 定义、T4/T5/T6 调用一致;`get_ocr_service()->OCRService|None` T2 定义、T3 使用一致;`_describe_docx_images(document)->list[str]` T5 定义;`_replace_md_images(text)->str` / `_IMG_DATA_URI_RE` T6 定义;parser 顶部 `import base64` + `describe_image` import 在 T4 引入,T5/T6 复用同一 import(执行按 T4→T6 顺序,import 已在)。
