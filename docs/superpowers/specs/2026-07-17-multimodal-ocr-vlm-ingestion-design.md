# 设计:③ OCR+VLM 多模态文档摄取

> 日期:2026-07-17
> 范围:本 spec 只覆盖「③ 性能优化与多模态」的多模态部分(OCR+VLM 解决文档内嵌图片信息丢失)。① 检索管道(含 Redis 语义缓存,与"性能优化"重叠部分)另立 spec。
> 参考实现:`D:\Agent\ai-agent-interview-guide\project-python`(`app/infrastructure/ocr/ocr_service.py` + `app/etl/parser.py`)——借鉴其逻辑,不照搬其类外壳。

## 背景与信息丢失点

GEO2 现有 `app/domain/knowledge/parser.py`:

- `parse_pdf`:仅 `page.extract_text()` → **图片(图表/截图/扫描页)全部丢失**。
- `parse_docx`:仅段落 + 表格文本 → **内嵌图片全部丢失**。
- `parse_md` / `parse_txt`:纯文本。

内嵌图片里的架构图、数据趋势、UI 截图、扫描文字对检索完全不可见。③ 从 PDF/DOCX/MD 抽出内嵌图片 → **OCR(图中文字)+ VLM(图的语义描述)** → 合并回文本再进现有分块/向量化。

## 决策记录(来自澄清 + 参考实现)

- **沿用 GEO2 函数式 parser**:把图片处理**注入**现有 `parse_pdf`/`parse_docx`/`parse_md`,不搬参考的 `DocumentParser` 类。(设计选择;物理约束是 GEO2 用模块级函数 + `@_handle_parse_errors`。)
- **OCR + VLM 都做**(不砍成只 VLM),合并成 `[图片文字：…]` + `[图片描述：…]`,再不行退 `[图片：alt]`。
- **OCR = EasyOCR 本地**(ch_sim+en,懒加载单例,软失败返回空)。
- **VLM = provider Vision API**(OpenAI 兼容,`VISION_*` env 缺省回退现有 provider,软失败返回空)。

## ⚠️ 前置准备(物理约束,实施前必须处理)

- GEO2 venv **未装 easyocr**(已有 torch 2.13)→ `pip install easyocr`。
- EasyOCR 模型缓存 `~/.EasyOCR/model/` **当前只有 `temp.zip`,无解压 `.pth`**(下载中断)→ 需在**有网环境**补全:`craft_mlt_25k.pth`(检测)+ `zh_sim_g2.pth` + `english_g2.pth`(识别),或跑一次 EasyOCR 让其下完解压。
- **补全前 OCR 路一直软降级(跳过),功能不崩但不生效**;VLM 需 provider Vision 可达。

## 模块(尽量新增,少改现有)

| 模块 | 职责 |
|---|---|
| `app/services/multimodal/ocr_service.py` | EasyOCR 封装:懒加载单例 `reader`,`extract_text(image_bytes) -> str`(去重拼接,软失败返回空) |
| `app/services/multimodal/image_describe.py` | `describe_image(b64, mime, alt) -> str`:OCR + VLM 合并;`_vlm_describe(b64, mime) -> str` 走 Vision API |
| `app/domain/knowledge/parser.py`(改) | `parse_pdf` 加 `page.images` 遍历、`parse_docx` 加 rels/`a:blip` 遍历、`parse_md` 加 base64 data-uri 正则;各调 `describe_image` 拼入文本 |

## 数据流

```
上传文档 → parse_*(注入图片处理)
  PDF : page.extract_text() + 每张 page.images → describe_image → 拼进该页文本
  DOCX: 段落/表格文本 + doc.part.rels 中 a:blip 图片 → describe_image → 拼入
  MD  : ![](data:image/..;base64,..) 正则 → describe_image → 替换
→ 合并后文本 → 现有 chunker → 现有 embedding / 向量化(不改)
```

## 关键实现(借鉴参考逻辑)

- `describe_image`:先 EasyOCR 出文字(`[图片文字：…]`),再 Vision API 出语义描述(`[图片描述：…]`),合并;两者皆空退 `[图片：alt]`。
- `_vlm_describe`:OpenAI 兼容 `chat.completions.create`,content 含 `{"type":"image_url","image_url":{"url":"data:{mime};base64,{b64}"}}`;prompt 让其描述架构/流程/趋势/UI 等非文字信息,纯文字图回 "文字型图片"(判为无描述);`max_tokens=256, temperature=0.1`;不支持 image_url 的 provider → 软失败。
- PDF 图片:`page.images` → `img.data` / `img.image_type`(`/png`→`image/png`)。
- DOCX 图片:`doc.part.rels` 建 `rel_id→(bytes, mime)` 映射,遍历 body 的 `w:drawing` 里 `a:blip` 的 `r:embed`(含表格、`mc:AlternateContent`)。

## 降级链(沿用"绝不失败"风格)

- EasyOCR 模型缺失 / 加载失败 → OCR 路跳过(返回空),文本抽取不受影响。
- 无 Vision key / API 不支持 image_url → VLM 路跳过(软失败)。
- 两路都空 → 退 `[图片：alt]` 占位;**无图文档解析行为完全不变(向后兼容)**。
- 单张图失败不影响整篇;单页失败不影响整 PDF(沿用现有 per-page 容错 + `@_handle_parse_errors`)。

## 配置(settings 新增)

- `multimodal_enabled: bool = True`
- `ocr_languages: list[str] = ["ch_sim", "en"]`
- `ocr_gpu: bool = False`
- `vision_api_key: str = ""`(缺省回退现有 provider key)
- `vision_api_base: str = ""`
- `vision_model: str = ""`
- `vision_max_tokens: int = 256`

## 测试

- `ocr_service`:mock easyocr reader,验证 extract + 去重 + 软失败(reader 抛异常返回空)。
- `image_describe`:mock OCR + mock Vision client,验证合并格式 / OCR 空只留描述 / VLM 空只留文字 / 都空退占位。
- `parser`:构造带图 PDF/docx fixture 或 mock `page.images` / `doc.part.rels`,验证图片描述被拼进文本;**无图文档行为不变(回归)**。

## 交付物

1. `app/services/multimodal/` 模块 + 单测。
2. `parser.py` 三个解析函数注入图片处理。
3. `pyproject.toml` 加 `easyocr` 依赖;`.env.example` 加 `VISION_*` 配置。
4. 前置准备说明(easyocr 安装 + 模型补全)写入 README / 部署文档。

## 非目标

- 不改分块 / 向量化 / 检索(① 另管)。
- 不做视频 / 音频多模态。
- 不本地跑 VLM(用 provider Vision API)。
- 不引入 Unstructured 库(参考项目的可选增强,GEO2 本期不需要)。
