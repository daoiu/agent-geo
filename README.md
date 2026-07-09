# GEO Optimization Agent

白帽 GEO (生成引擎优化) 诊断工具。输入品牌信息 → 自动生成 GEO 健康度诊断报告。

## 快速开始

```bash
# 1. 复制环境变量模板并填入 API key
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY

# 2. 启动服务
docker-compose up --build

# 3. 访问
# 前端: http://localhost:5173
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

## 文档

- 设计文档: `docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md`
- 实施计划: `docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md`

## 开发

参见实施计划中的 task-by-task 步骤。
