# 手动验证清单 — GEO Agent v0.5

发布前必跑 7 个场景。

## 前置条件

```bash
cd "D:/GEO2"
# 编辑 .env，确保 DEEPSEEK_API_KEY 已设置
docker-compose up --build -d
sleep 60  # 首次启动需加载 bge 模型
```

## 场景

### 1. 混合检索召回率提升 ✅

1. 在 v0.2 上传 5 个文档到知识库(内容关于"产品续航")
2. 在知识库详情页搜索"长续航"
3. **预期**:
   - 找到含"电池容量"、"续航"等的段落
   - 召回比 v0.2 纯关键词搜索更多

### 2. 启动时 lazy 向量化 ✅

1. 在 v0.5 之前上传了文档到 v0.2
2. 启动 v0.5
3. 看日志 `v0.5_reindex_done`
4. **预期**:日志显示 `total_kbs` 和 `total_indexed`

### 3. 新增文档自动向量化 ✅

1. 在 v0.2 上传新文档
2. 等待解析完成
3. 立即用新文档的关键词搜索
4. **预期**:新文档的 chunk 出现在搜索结果中(说明已向量化)

### 4. 删除文档级联清理 ✅

1. 在 v0.2 删除一个文档
2. 检查 ChromaDB 内部
3. **预期**:对应的 chunk 向量已从 ChromaDB 移除

### 5. ChromaDB 不可用时降级 ✅

1. 临时删除 `./data/chroma/` 目录权限
2. 触发一次搜索
3. **预期**:
   - 仍然返回结果(纯关键词)
   - 日志显示 `hybrid_search_failed, falling back to keyword`

### 6. 单次 hybrid search < 500ms ✅

1. 准备 100 chunks
2. 用 stopwatch 测搜索延迟
3. **预期**:< 500ms

### 7. v0.4 agent 工具升级 ✅

1. 在 agent chat 问"小米的售后"
2. 看 agent 调用的 `search_knowledge` 工具结果
3. **预期**:能找到"退换货"、"保修"等段落(语义匹配)

## 通过标准

7 项全过 → v0.5 完成。

## v0.5 新增自动化覆盖(spec §7)

- `test_pending_index_v05.py`:`pending_index` 列存在 + 默认 False + 迁移幂等
- `test_api_knowledge_v05.py`:
  - DELETE 文档路由调 `VectorIndex.delete_chunks`
  - ChromaDB 删除失败不破坏 API
  - parser_worker 在解析后调 `VectorIndex.add_chunks`
  - ChromaDB 写入失败时 mark `pending_index=True` (ReindexService 启动补齐)
