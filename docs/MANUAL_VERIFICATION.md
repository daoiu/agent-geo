# 手动验证清单 — GEO Agent v0.1

发布前必跑 4 个场景，全部通过才能认为 MVP v0.1 "完成"。

## 前置条件

```bash
cd "D:/GEO2"
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
docker-compose up --build -d
sleep 30  # 等待服务启动
```

## 场景 1: 完整诊断流程

1. 浏览器打开 http://localhost:5173
2. 点击 "新建诊断"
3. 步骤 1 填：
   - 品牌名: "小米"
   - 行业: "消费电子"
   - 官网: "https://www.mi.com"
4. 步骤 2 填 3 个问题：
   - "小米手机怎么样"
   - "小米14值得买吗"
   - "小米 vs 华为"
5. 步骤 3 点 "提交诊断"

**预期**：
- 进度页出现，显示阶段切换（crawling → querying_llm → scoring → completed）
- 90 秒内跳转到报告页
- 报告页显示：综合分数、雷达图、≥3 条建议
- 点 "下载 PDF" 下载到有效 PDF 文件，中文不乱码

## 场景 2: 网站无法访问

1. 步骤 1 填官网: "https://this-domain-does-not-exist-xyz123.com"
2. 提交

**预期**：
- 进度页显示 "诊断失败"
- 错误信息包含 "官网无法访问"

## 场景 3: LLM 部分失败

1. 编辑 .env，设置 `DEEPSEEK_API_KEY=sk-invalid-key`
2. `docker-compose restart backend`
3. 提交一个真实品牌的诊断

**预期**：
- 任务最终标记 failed 或 completed with mention_rate=N/A
- 网页报告能看到 LLM 错误信息（不阻断整个报告生成）
- mention_rate 标注 "N/A" 或显示 "0% (0/0)"

## 场景 4: PDF 下载与中文渲染

承接场景 1 的报告：

1. 在报告页点 "下载 PDF"
2. 用 PDF 阅读器打开

**预期**：
- 文件名: `geo-report-<id 前 8 位>.pdf`
- 文件大小 > 10KB
- 中文显示正常（Noto Sans CJK 字体）
- 包含：标题、综合分、五维度、建议清单

## 通过标准

- [ ] 场景 1 通过
- [ ] 场景 2 通过
- [ ] 场景 3 通过
- [ ] 场景 4 通过

4 项全过才能标记 v0.1 完成。
