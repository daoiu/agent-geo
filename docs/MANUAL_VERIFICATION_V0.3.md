# 手动验证清单 — GEO Agent v0.3

发布前必跑 11 个场景。

## 前置条件

```bash
cd "D:/GEO2"
# 编辑 .env，确保以下都已设置：
# - DEEPSEEK_API_KEY
# - ENCRYPTION_KEY  (运行: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
# - SMTP_HOST, SMTP_USER, SMTP_PASSWORD 等
docker-compose up --build -d
sleep 30
```

## 场景

### 1. 添加 WordPress 凭证 ✅

1. 进入 /publishers
2. 添加凭证，填入真实 WordPress Application Password
3. 点"测试"按钮
4. **预期**：弹窗显示"连接成功"

### 2. 发布一篇文章（成功）✅

1. 准备一个真实 WordPress 站点
2. 从 v0.2 选一个 approved Article
3. 在 /publishes 创建发布任务
4. 等待任务完成
5. **预期**：status=success，显示 remote_url；登录 WordPress 后台可见

### 3. 发布失败（错误凭证）❌

1. 添加一个错误密码的凭证
2. 尝试用它发布
3. **预期**：status=failed，error_message 含"认证失败"

### 4. 重试失败发布 ✅

1. 复用场景 3 的失败任务
2. 修复凭证后点"重试"
3. **预期**：任务重新运行

### 5. 创建 daily 监测 ✅

1. 进 /monitors/new
2. 填入品牌、3-5 个问题、daily
3. **预期**：监测任务出现在列表

### 6. 立即跑一次监测 ✅

1. 进监测详情
2. 点"立即跑"
3. 等待几秒
4. **预期**：趋势图出现第一个数据点

### 7. 监测变化触发邮件 ⚠️

1. 修改数据库人为制造大变化（手动改 mention_rate）
2. 等待下次执行
3. **预期**：收件箱收到"提及率上升/下降 X%"邮件

### 8. 暂停 / 恢复监测任务 🛑

1. 进监测详情
2. 修改 is_active 字段（v0.3 暂不提供 UI，需要 SQL 修改）
3. **预期**：暂停后不再自动跑

### 9. 进程重启后监测调度恢复 ✅

1. 创建几个 daily 监测任务
2. `docker-compose restart backend`
3. 等 30 秒
4. **预期**：监测继续按计划执行（看 last_run_at 是否更新）

### 10. 删凭证有发布任务 ❌

1. 创建凭证 + 发布任务
2. 尝试删凭证
3. **预期**：409 错误，提示"有 N 个发布任务"

### 11. 发未审核文章 ❌

1. 选一个 review_status=pending 的 Article
2. 尝试发布
3. **预期**：422 错误，提示"article must be approved"

## 通过标准

11 项全过 → v0.3 完成。
