"""从 brands 表 + 精选术语生成 jieba 领域词典 data/geo_terms.txt。

词典格式:每行 `词 词频 词性`,词频给 100 保证不被切碎。

用法:cd backend && python -m scripts.seed_geo_terms
输出:backend/data/geo_terms.txt(写入品牌名 + 精选技术术语去重集合)
"""
import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models.orm import ReportORM

# 精选技术术语(手工维护)
TECH_TERMS = [
    "LangChain", "LangGraph", "GPT-4o", "Claude-3.5", "ChromaDB",
    "Cross-Encoder", "BM25", "RRF", "HyDE", "RAGAS", "bge-reranker",
    "生成式引擎优化", "向量检索", "混合检索", "重排",
]


async def main():
    """主入口:从 DB 取品牌名 + 精选术语 → 写 geo_terms.txt。

    项目未独立建 BrandORM,品牌名存在 ReportORM.brand_name(诊断报告的品牌字段),
    用 DISTINCT 提取去重集合,避免重复写入。
    """
    terms: set[str] = set(TECH_TERMS)
    async with get_session_factory()() as session:
        rows = await session.execute(select(ReportORM.brand_name).distinct())
        terms.update(r for (r,) in rows.all() if r)
    # 锚到 backend/data/(脚本从 backend/ 跑,工作目录就是 backend/)
    out = Path("data/geo_terms.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"{t} 100 n\n" for t in sorted(terms)), encoding="utf-8")
    print(f"写入 {len(terms)} 个领域词 → {out}")


if __name__ == "__main__":
    asyncio.run(main())