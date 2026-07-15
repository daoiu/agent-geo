# 设置页模型配置 — 设计稿

> 创建日期: 2026-07-15
> 状态: 设计稿(待用户审阅)
> 配套实施 plan: 待 writing-plans 阶段生成

---

## 1. 背景与动机

### 1.1 当前差距

后端 `backend/app/core/config.py` 已定义完整的 LLM 配置(各 provider 的 API key / base_url / model、三档 `model_tier_cheap/standard/premium`、`fallback_chain`、`llm_providers`),但**全部走环境变量 + `.env` 文件 + `lru_cache` 单例**。后果:

- 用户要改模型必须 SSH 到服务器编辑 `.env` 然后重启后端进程
- 没有运行时热重载通道
- 非技术市场人员根本无法自助调模型

前端 `frontend/src/pages/Settings.tsx` 当前是只读状态卡(后端连通性 / 前端版本 / 模块入口 / 关于),P0 注释明确写 "P1+ will surface mutations"。

### 1.2 用户原话

- 「在设置里添加模型的配置 点击保存后立即生效」

### 1.3 目标

让用户在 `/settings/models` 页面可以编辑所有 provider 的 API key / base_url / model、三档 tier 选择、fallback chain、默认 provider 顺序,保存后**下一次 LLM 调用**就用到新值,无需重启进程。

---

## 2. 设计决策

| 维度 | 决定 |
|---|---|
| **配置范围** | 全部(provider api_key / base_url / model + 三档 tier + fallback_chain + llm_providers) |
| **生效语义** | 后端热重载,下一次 LLM 调用生效(正在跑的 agent 任务不受影响) |
| **页面归属** | 新增独立页面 `/settings/models`(不混入现有 `/settings/general`) |
| **持久化** | 独立 JSON 文件 `data/model_config.json`,与 `.env` 并存 |
| **API key 安全** | Fernet 加密落盘(复用 `app/domain/security/encryption.py`)+ 前端掩码显示 |
| **覆盖策略** | 启动优先 `.env`,运行时优先 JSON;JSON 缺字段 fall back 到 `.env`;JSON 校验失败降级不阻塞启动 |
| **重置** | 提供 "重置为 .env 默认值" 按钮,删除 JSON 文件 |
| **不可写 .env** | UI 改动只写 JSON,绝不回写 `.env`(部署期配置与运行时配置解耦) |

### 2.1 不在范围内(YAGNI)

- 多用户权限 / 角色管理(项目无 auth,PreferencesStore 也是单用户模式)
- 编辑 .env 的能力(反模式,部署期与运行时职责分离)
- provider 健康检查 / 自动切换(本期纯手动)
- 模型使用量统计 / 限额(已有 CostDashboard,不在此 spec 范围)

---

## 3. 架构总览

### 3.1 系统边界

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                        │
│  /settings/models 页面 ── settingsApi ── PATCH /api/settings/models │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP (auth_headers + X-Device-Id)
┌────────────────────────────▼────────────────────────────────────┐
│                  Backend (FastAPI)                                │
│  SettingsModelEndpoint (新)                                        │
│       ├─ GET   /api/settings/models                               │
│       ├─ PATCH /api/settings/models                               │
│       └─ POST  /api/settings/models/reset                         │
│              │                                                    │
│              ▼                                                    │
│       ModelConfigStore (新)                                       │
│       ├─ data/model_config.json (Fernet 加密)                     │
│       ├─ RLock + 内存缓存                                         │
│       └─ update / get / reset 接口                                │
│              │                                                    │
│              ▼                                                    │
│       Settings.merge_runtime_overrides() (扩展)                  │
│       get_settings.cache_clear() (lru_cache 失效)                 │
│              │                                                    │
│              ▼                                                    │
│  resolve_providers() / select_model() / llm_client.py  (零改动) │
└─────────────────────────────────────────────────────────────────┘
```

**关键**: `PROVIDERS_META`、`resolve_providers()`、`select_model()` 等所有读取 LLM 配置的代码**零改动** —— 它们通过 `get_settings()` 拿到合并后的 Settings 实例。

### 3.2 模块清单

| 模块 | 路径 | 状态 | 职责 |
|------|------|------|------|
| `ModelConfigStore` | `backend/app/core/model_config_store.py` | 新增 | JSON 持久化 + 内存缓存 + RLock + 加密/解密 |
| `Settings.merge_runtime_overrides()` | `backend/app/core/config.py` | 扩展 | 把 store 快照合并进 Settings 实例属性 |
| `SettingsModelEndpoint` | `backend/app/api/settings_model.py` | 新增 | GET / PATCH / reset 三个路由 |
| API 注册 | `backend/app/main.py` | 扩展 | `app.include_router(...)` |
| `settingsApi` | `frontend/src/api/settings.ts` | 新增 | `getModelConfig` / `updateModelConfig` / `resetModelConfig` |
| `ModelsSettings` 页面 | `frontend/src/pages/ModelsSettings.tsx` | 新增 | 表单 + 保存 + 重置 + 掩码 + 错误回显 |
| 路由表 | `frontend/src/routes.ts` | 扩展 | `settingsModels: '/settings/models'` |
| 应用挂载 | `frontend/src/App.tsx` | 扩展 | 路由组件 |
| 侧边栏 | `frontend/src/components/layout/navConfig.tsx` | 扩展 | "设置" 分组下加 "模型配置" 子项 |

---

## 4. 数据模型

### 4.1 磁盘文件 `data/model_config.json`

```json
{
  "providers": {
    "deepseek": {
      "api_key": "gAAAAABl...   (Fernet 加密密文)",
      "base_url": "https://api.deepseek.com/v1",
      "model": "deepseek-chat"
    },
    "kimi": {
      "api_key": "gAAAAABl...",
      "base_url": "https://api.moonshot.cn/v1",
      "model": "moonshot-v1-8k"
    },
    "openai": {
      "api_key": "",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4o-mini"
    }
  },
  "tiers": {
    "cheap": "deepseek",
    "standard": "deepseek",
    "premium": "deepseek"
  },
  "fallback_chain": ["deepseek", "kimi"],
  "llm_providers": ["deepseek"],
  "updated_at": "2026-07-15T12:00:00+00:00"
}
```

**要点**:
- `providers` 始终包含 `PROVIDERS_META` 注册的全部 provider(deepseek/kimi/openai),即便没配 key 也保留空字符串
- `api_key` 落盘前必须 Fernet 加密;读出时解密
- `tiers` 三档 provider 名必须是 `providers` 的子集,否则校验失败并降级
- `fallback_chain` / `llm_providers` 是列表(比 env 里逗号分隔更便于前端编辑)

### 4.2 JSON → Settings 字段映射

| JSON 路径 | Settings 属性 |
|---|---|
| `providers.<name>.api_key` (解密后) | `<name>_api_key` |
| `providers.<name>.base_url` | `<name>_base_url` |
| `providers.<name>.model` | `<name>_model` |
| `tiers.cheap` | `model_tier_cheap` |
| `tiers.standard` | `model_tier_standard` |
| `tiers.premium` | `model_tier_premium` |
| `fallback_chain` | `fallback_chain` (逗号分隔) |
| `llm_providers` | `llm_providers` (逗号分隔) |

### 4.3 API DTO

**GET `/api/settings/models` 响应**:

```json
{
  "providers": [
    { "name": "deepseek", "base_url": "...", "model": "...", "api_key_masked": "sk-***abc123", "api_key_set": true },
    { "name": "kimi",     "base_url": "...", "model": "...", "api_key_masked": "",            "api_key_set": false }
  ],
  "tiers": { "cheap": "deepseek", "standard": "deepseek", "premium": "deepseek" },
  "fallback_chain": ["deepseek", "kimi"],
  "llm_providers": ["deepseek"],
  "source": "json",
  "updated_at": "2026-07-15T12:00:00+00:00"
}
```

> `source` 字段取值:`"env"` 表示当前 Settings 完全来自 `.env`(无 JSON 覆盖);`"json"` 表示已存在 `data/model_config.json` 且至少有一个字段覆盖 .env。

**PATCH 请求 payload**:

```json
{
  "providers": [
    { "name": "deepseek", "api_key": "sk-新值或省略", "base_url": "...", "model": "deepseek-reasoner" }
  ],
  "tiers": { "cheap": "deepseek", "standard": "deepseek", "premium": "deepseek" },
  "fallback_chain": ["deepseek", "kimi"],
  "llm_providers": ["deepseek"]
}
```

**PATCH 语义**:
- `api_key` 字段为空字符串或缺失 → 视为"不改 key"(避免前端为掩码渲染出的空字符串覆盖真实 key)
- `api_key` 字段为非空 → 替换(前端明文发送 → 后端加密落盘)
- 其它字段按值覆盖

**POST `/api/settings/models/reset`**: 删除 `data/model_config.json`,清空 lru_cache,下一次 `get_settings()` 退回纯 .env。

### 4.4 校验规则

| 规则 | 失败行为 |
|---|---|
| `tiers.*` 必须是 `PROVIDERS_META` 已注册名 | 422 + 字段级错误 `code=unknown_provider` |
| `fallback_chain` 每个元素必须已注册 | 422 |
| `llm_providers` 同上 | 422 |
| provider 的 `base_url` 必须是 http(s) URL | 422 `code=invalid_base_url` |
| provider 的 `model` 非空字符串 | 422 `code=empty_model` |
| `encryption_key` 为空字符串时尝试保存非空 api_key | 422 `code=encryption_key_missing` |
| 进程内并发 PATCH(双击保存导致 RLock 排队后 stale payload) | 409 `code=concurrent_update` |

---

## 5. 数据流

### 5.1 启动时

```
uvicorn 启动
  └─ main.py: get_settings()  ←── 首次构造
       ├─ BaseSettings 从 .env 读 baseline
       ├─ ModelConfigStore._load() 读 data/model_config.json
       │     ├─ 文件不存在 → store 空,仅 .env 生效
       │     ├─ 文件存在 → JSON 解密 + 解析进 _cache
       │     └─ JSON 缺字段 → fall back 到 .env
       └─ Settings.merge_runtime_overrides(store.snapshot())
              ├─ 遍历 store.providers,对每个字段 setattr
              ├─ 校验 tier/chain/providers 都在 PROVIDERS_META 内
              └─ 校验失败 → 跳过该字段 + warning log + 保留 .env 值
     ←── 返回 Settings 实例
  └─ 后续调用命中 lru_cache
```

**关键**: JSON 与 .env 字段冲突时 **JSON 优先**;JSON 字段缺失时 fall back 到 .env;JSON 校验失败时降级到 .env 而不是拒绝启动。

### 5.2 GET 请求(前端拉配置)

```
前端 ModelsSettings mount
  └─ settingsApi.getModelConfig()
       └─ GET /api/settings/models
            └─ SettingsModelEndpoint.get()
                 ├─ settings = get_settings()
                 ├─ 组装 providers 列表(按 PROVIDERS_META 顺序)
                 │     ├─ base_url / model 从 settings 取(已 merge)
                 │     ├─ api_key_set = bool(settings.<name>_api_key)
                 │     └─ api_key_masked = mask_key(settings.<name>_api_key)
                 ├─ tiers / fallback_chain / llm_providers 同源
                 ├─ source = "json" if store.has_overrides() else "env"
                 └─ 返回 DTO
```

**掩码规则**: `mask_key(value)` 当 `value` 长度 ≥ 8 时返回 `value[:3] + "***" + value[-3:]`;否则返回 `"***"`;空字符串返回 `""`。

### 5.3 PATCH 保存(核心 — 热重载)

```
前端点击"保存"
  └─ settingsApi.updateModelConfig(payload)
       └─ PATCH /api/settings/models
            └─ SettingsModelEndpoint.patch(body)
                 ├─ 1. 校验 schema(Pydantic)
                 ├─ 2. ENCRYPTION_KEY 非空检查(仅在 payload 含非空 api_key 时)
                 ├─ 3. store.update(payload)
                 │     ├─ api_key 非空 → Fernet 加密
                 │     ├─ api_key 空 / 缺失 → 保留旧密文
                 │     ├─ 原子写(写到 .tmp 再 rename)
                 │     └─ 更新内存 _cache
                 ├─ 4. get_settings.cache_clear()
                 ├─ 5. settings = get_settings()  ←── 触发下次 merge
                 ├─ 6. 记录 audit log
                 └─ 7. 返回新 DTO(前端无需再 GET)
```

**前端保存后**:
- 用响应里的新 DTO 直接替换表单 state(乐观更新)
- 顶部 toast: "已保存,下次 LLM 调用生效"
- source 字段如果从 "env" 变成 "json",显示徽标 "当前配置来自运行时覆盖(重启后仍生效)"

### 5.4 重置

```
前端点击"重置为 .env 默认值"
  └─ 二次确认 dialog
       └─ settingsApi.resetModelConfig()
            └─ POST /api/settings/models/reset
                 ├─ store.delete_file()
                 ├─ get_settings.cache_clear()
                 ├─ get_settings() 重新构造 → 纯 .env
                 └─ 返回新 DTO
```

### 5.5 热路径保证

`resolve_providers()` / `select_model()` 调用点仍然 `get_settings()`,**不感知 store 存在** —— store 写盘后已经 `cache_clear()` 并触发下次 merge,所以下一次调用就拿到新值。

**竞态边界**: cache_clear 与并发 LLM 调用之间。如果 in-flight 请求已拿到旧 Settings 实例(局部变量),它会用旧值完成 —— 这是**用户接受**的边界(语义选了"下一次调用生效")。

---

## 6. 错误处理

### 6.1 启动阶段

| 场景 | 行为 |
|---|---|
| `.env` 不存在 | BaseSettings 用默认值(不动) |
| `data/model_config.json` 不存在 | store 空,仅 .env |
| JSON 解析失败 | **降级**: store 跳过文件 + warning log + 走纯 .env;不阻塞启动 |
| JSON 字段缺漏 | 该字段 fall back 到 .env;其它字段正常合并 |
| JSON tier 引用未注册 provider | **降级**: 跳过该 tier 字段 + warning + 保留 .env tier 值 |
| JSON 加密密文损坏(Fernet 解密失败) | **降级**: 该 provider 的 api_key 视为空,不影响 base_url/model |
| `ENCRYPTION_KEY` 为空但 JSON 含密文 | 同上降级 |
| `ENCRYPTION_KEY` 改了导致旧密文解密失败 | 同上 + UI 显示"加密密钥变更,需要重新输入 API key" |

### 6.2 PATCH 请求错误

| 场景 | HTTP | code |
|---|---|---|
| `tiers.premium` = "minimax"(未注册) | 422 | `unknown_provider` |
| `fallback_chain` 含未注册 provider | 422 | `unknown_provider` |
| `base_url` 不是 http(s) | 422 | `invalid_base_url` |
| `model` 为空字符串 | 422 | `empty_model` |
| `ENCRYPTION_KEY` 空 + payload 含非空 api_key | 422 | `encryption_key_missing` |
| 磁盘写失败(权限 / 磁盘满) | 500 | `persist_failed` |
| 进程内并发 PATCH(双击保存) | 409 | `concurrent_update` |

**字段级回显**: 422 响应的 `details` 字段做成 `[{field: "providers[0].base_url", code: "invalid_base_url", message: "..."}]`,前端 `setError` 挂到对应输入框。

### 6.3 加密相关

| 场景 | 行为 |
|---|---|
| `encryption_key` 为空 → 无法保存新 key | PATCH 时 422 拦截;UI 顶部黄色横幅 "加密密钥未配置,暂无法保存 API key;其它字段可保存" |
| 加密 key 改了 → 旧 key 解密失败 | 见 §6.1 降级;UI 在受影响 provider 卡片显示红点 + "API key 失效,请重新输入" |
| PATCH 时 `api_key` 字段非空但与磁盘值解密后一致 | 仍然写盘(避免脏检查逻辑) |
| PATCH 时 `api_key` 空字符串 | 保留旧 key(不覆盖、不删除密文) |
| PATCH 时 `api_key` 为 null | 同上 |

### 6.4 竞态

| 场景 | 处理 |
|---|---|
| 两个并发 PATCH | RLock 串行化 store 操作;后到达的 PATCH 等锁;不会出现交叉写 |
| cache_clear 与 in-flight LLM 调用 | 已取到 Settings 实例的请求继续用旧值完成;下一请求拿到新值(符合"下一次调用生效") |
| 进程崩溃在 store.update 之后、cache_clear 之前 | 下次启动 store 从磁盘读到新值,自动 merge(自愈) |

### 6.5 前端 UX

- 字段错误: 红框 + 字段下方错误文案
- 全局错误: 顶部 error toast,5s 自动消失,可手动关闭
- 保存中: 按钮 disabled + 旋转图标;不可重复点击
- 网络断开: toast "网络错误,请检查连接"

---

## 7. 测试矩阵

### 7.1 后端单元测试

`backend/tests/test_model_config_store.py`(10 用例)
- `test_store_creates_file_on_first_save` — 首次写入自动 mkdir data/,原子写
- `test_store_encrypts_api_key_on_disk` — 落盘后 api_key 是 Fernet 密文
- `test_store_decrypts_api_key_on_read` — store.get_provider(name).api_key 返回明文
- `test_store_preserves_old_key_when_payload_empty` — PATCH api_key="" 不覆盖
- `test_store_preserves_old_key_when_payload_missing` — PATCH payload 无 api_key 不覆盖
- `test_store_loads_missing_file_as_empty` — 文件不存在 → 空 cache
- `test_store_skips_corrupted_json` — 写入垃圾 → load 不抛 + cache 空 + warning
- `test_store_survives_invalid_ciphertext` — 手写坏密文 → provider 视为空 key,其它字段正常
- `test_store_thread_safe_under_concurrent_writes` — 10 线程并发 patch,最终文件内容是某次完整 payload
- `test_store_reset_clears_file` — reset → 文件删除 + cache 清空

### 7.2 后端 Settings merge 测试

`backend/tests/test_settings_merge.py`(7 用例)
- `test_settings_uses_env_when_json_missing` — 无 JSON → 完全走 .env
- `test_settings_json_overrides_env_per_field` — JSON 只覆盖 deepseek_api_key,其它字段走 .env
- `test_settings_merges_all_provider_keys` — JSON 覆盖 deepseek/kimi/openai 全部字段
- `test_settings_invalid_tier_falls_back_to_env` — JSON `tiers.premium="minimax"` → premium 走 .env
- `test_settings_invalid_fallback_falls_back_to_env` — 同上对 fallback_chain
- `test_settings_cache_cleared_after_store_update` — store.update 后 `get_settings()` 字段为新值
- `test_settings_merges_each_call_after_clear` — `cache_clear` 后连续两次 `get_settings()` 都返回新值

### 7.3 后端 API 集成测试

`backend/tests/test_api_settings_model.py`(15 用例)
- `test_get_returns_providers_from_settings` — GET 200,providers 顺序与 PROVIDERS_META 一致
- `test_get_masks_api_key_when_set` — api_key_set=true → `sk-***abc123` 形式
- `test_get_omits_mask_when_unset` — api_key_set=false → api_key_masked=""
- `test_get_reports_source_json_when_override_exists` — 有 JSON → source="json"
- `test_get_reports_source_env_when_no_override` — 无 JSON → source="env"
- `test_patch_updates_store_and_clears_cache` — PATCH 200 + 文件更新 + `get_settings().deepseek_api_key` 为新值
- `test_patch_rejects_unknown_provider_in_tier` — tiers.premium="minimax" → 422 `unknown_provider`
- `test_patch_rejects_invalid_base_url` — base_url="not-a-url" → 422 `invalid_base_url`
- `test_patch_rejects_empty_model` — model="" → 422
- `test_patch_rejects_when_encryption_key_missing_and_payload_has_key` — ENCRYPTION_KEY="" + 非空 api_key → 422
- `test_patch_allows_non_key_fields_when_encryption_key_missing` — ENCRYPTION_KEY="" + 仅 base_url/model → 200
- `test_patch_empty_api_key_does_not_clear_existing` — 已设 key,PATCH api_key="" → 旧 key 保留
- `test_patch_missing_api_key_does_not_clear_existing` — payload 无 api_key → 旧 key 保留
- `test_reset_clears_overrides_and_falls_back_to_env` — POST /reset → 文件删除 + 退回 .env
- `test_patch_returns_updated_dto` — PATCH 响应 body 与随后 GET 一致(无需再 GET)

### 7.4 前端单元测试

`frontend/src/pages/ModelsSettings.test.tsx`(13 用例)
- `test_renders_loading_skeleton_on_mount`
- `test_renders_three_provider_cards_after_load` — deepseek/kimi/openai
- `test_api_key_input_shows_mask_when_set` — placeholder = `sk-***xxx`,value 为空
- `test_api_key_input_shows_empty_when_unset` — placeholder = "尚未设置"
- `test_changing_base_url_or_model_marks_dirty` — 输入触发 dirty state + 保存按钮 enable
- `test_saving_with_no_api_key_field_preserves_mask_warning` — 用户没填 api_key → 提交时不发该字段
- `test_saving_with_new_api_key_sends_value` — 用户填了新 api_key → payload 含 api_key
- `test_save_success_shows_toast_and_updates_form` — PATCH 200 → toast + 表单值替换
- `test_save_validation_error_highlights_field` — 422 + details → 红框 + 错误文案
- `test_save_encryption_key_missing_shows_banner` — 422 `encryption_key_missing` → 黄色横幅
- `test_reset_button_requires_confirmation` — 点击重置 → 二次确认 dialog
- `test_reset_clears_overrides_and_shows_env_badge` — 二次确认 → source 从 "json" 变 "env"
- `test_concurrent_save_disables_button` — 保存中按钮 disabled

### 7.5 前端 API 层测试

`frontend/src/api/settings.test.ts`(4 用例)
- `test_get_model_config_calls_correct_path`
- `test_update_model_config_sends_patch`
- `test_reset_model_config_calls_correct_path`
- `test_api_error_propagates_status_and_code`

### 7.6 回归覆盖

确保现有测试**不破**:
- `test_providers.py`(resolve_providers 不变)
- `test_adaptive_model.py`(select_model 不变)
- `test_fallback_strategy.py`(fallback 链不变)
- `test_react_loop*.py`(agent loop 拿不到 settings 变更时的行为不变)

---

## 8. 实施路径(预演,正式 plan 在 writing-plans 阶段)

1. **后端骨架** — `model_config_store.py` + `Settings.merge_runtime_overrides` + 测试(7.1 + 7.2)
2. **后端 API** — `settings_model.py` + main.py 注册 + 测试(7.3)
3. **前端 API 层** — `api/settings.ts` + 测试(7.5)
4. **前端页面** — `ModelsSettings.tsx` + 路由 + 侧栏 + 测试(7.4)
5. **回归验证** — 跑 7.6 现有测试 + tsc + vitest 全套

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| `lru_cache` 失效窗口期与并发 LLM 调用竞态 | 已取到旧 Settings 实例的请求用旧值完成(用户接受) |
| `ENCRYPTION_KEY` 改了导致旧 key 解密失败 | 降级为 key 为空 + UI 提示重新输入 |
| JSON 文件写崩后磁盘半写 | 原子写(.tmp + rename) |
| 前端表单误把掩码空串当"清空 key"提交 | PATCH 语义:`api_key=""` 或缺失都视为"不改" |
| Settings 与 store 不同步(代码 bug) | 测试 7.2 + 7.3 共 7 个用例覆盖 merge 路径 |

---

## 10. 验收标准

- [ ] §7.1 + 7.2 + 7.3 + 7.4 + 7.5 全部用例通过
- [ ] §7.6 现有测试无回归
- [ ] tsc / pyright 无新增错误
- [ ] 手动跑一遍 §5.5 数据流(后端启动 → PATCH → 触发 LLM 调用 → 日志确认新 model)
- [ ] 重启后端进程,GET 仍是新值(持久化生效)
- [ ] POST /reset 后,重启进程,GET 退回 .env 值

---

## 11. 后续阶段(不在本 spec)

- 密钥分项目 / 多环境隔离
- 运行时热切换生效于正在跑的 agent 任务(本期放弃)
- 模型使用量统计接入 / 限额告警
- provider 健康检查 + 自动降级