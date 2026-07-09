# GEO 优化 Agent v0.1

白帽 GEO（生成引擎优化）诊断工具。输入品牌信息 → 自动生成 GEO 健康度诊断报告。

## 功能

- 一键诊断品牌的 GEO 健康度
- 5 个维度的评分卡（权威度、内容相关性、结构、更新频率、数据可验证性）
- AI 平台实测的提及率（DeepSeek / Kimi）
- 可执行的优化建议清单
- 网页报告 + PDF 下载

## 快速开始

### 前置条件

- Docker + docker-compose
- 一个 DeepSeek 或 Kimi 的 API key

### 启动

```bash
git clone <repo>  # 或解压项目目录
cd GEO2
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY
docker-compose up --build
```

访问：
- 前端: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 开发

### 项目结构

```
GEO2/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 入口
│   │   ├── api/             # REST 路由
│   │   ├── core/            # 配置 + DB
│   │   ├── domain/          # 业务逻辑（crawler, llm, scorer, renderer）
│   │   ├── models/          # Pydantic + SQLAlchemy
│   │   ├── repositories/    # DB 访问层
│   │   ├── services/        # 编排
│   │   ├── tasks/           # 异步 worker
│   │   └── templates/       # Jinja2 PDF 模板
│   └── tests/
├── frontend/                # React + Vite 前端
│   ├── src/
│   │   ├── pages/           # 路由页面
│   │   ├── components/      # 复用组件
│   │   ├── api/             # API 客户端
│   │   └── types/           # TypeScript 类型
│   └── tests/e2e/
├── docs/
│   ├── superpowers/
│   │   ├── specs/           # 设计文档
│   │   └── plans/           # 实施计划
│   └── MANUAL_VERIFICATION.md
├── docker-compose.yml
└── .env.example
```

### 后端开发

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
pytest -v  # 跑测试
```

启动开发服务器：

```bash
uvicorn app.main:app --reload --port 8000
```

### 前端开发

```bash
cd frontend
npm install
npm run dev  # 启动 dev server (端口 5173)
```

类型检查：

```bash
npm run lint
```

E2E 测试：

```bash
npm run test:e2e
```

### 启用 Kimi 作为第二个 LLM

编辑 `.env`：

```bash
KIMI_API_KEY=sk-your-kimi-key
LLM_PROVIDERS=deepseek,kimi
```

重启后端：

```bash
docker-compose restart backend
```

## 文档

### v0.1（当前版本）

- 设计文档: [docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md](docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md)
- 实施计划: [docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md](docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md)
- 手动验证清单: [docs/MANUAL_VERIFICATION.md](docs/MANUAL_VERIFICATION.md)

### 后续版本规划

下列文档为 v0.2—v0.5 的蓝图，属于未来迭代范围，非 v0.1 交付物：

| 版本 | 设计文档 | 实施计划 |
|---|---|---|
| v0.2 内容改写助手 | [spec](docs/superpowers/specs/2026-07-09-geo-agent-v0.2-design.md) | [plan](docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.2.md) |
| v0.3 完整闭环 | [spec](docs/superpowers/specs/2026-07-10-geo-agent-v0.3-design.md) | [plan](docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.3.md) |
| v0.4 Agent 化 | [spec](docs/superpowers/specs/2026-07-10-geo-agent-v0.4-design.md) | [plan](docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md) |
| v0.5 向量检索升级 | [spec](docs/superpowers/specs/2026-07-10-geo-agent-v0.5-design.md) | [plan](docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.5.md) |

## 合规说明

本工具**只做诊断和建议**，不做内容伪造、AI 投毒等黑帽 GEO 操作。所有建议基于公开方法论，不构成具体法律/财务/医疗建议。

详见设计文档 §9 合规与边界。

## 许可证

MIT（待定）
