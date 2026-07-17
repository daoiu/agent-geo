"""领域分词:加载 GEO 用户词典 + 统一 jieba 切词入口。

专有名词(品牌名/模型名/技术术语)靠 userdict 防切碎,保障 BM25/关键词召回。
"""
from __future__ import annotations

from pathlib import Path

import jieba
import structlog

logger = structlog.get_logger()
_loaded = False


def load_domain_dict(path: str | Path) -> bool:
    """加载领域词典(幂等)。文件不存在返回 False,不抛。"""
    global _loaded
    p = Path(path)
    if not p.exists():
        logger.warning("geo_userdict_missing", path=str(p))
        return False
    jieba.load_userdict(str(p))
    _loaded = True
    logger.info("geo_userdict_loaded", path=str(p))
    return True


def tokenize(text: str) -> list[str]:
    """jieba 切词,去空白与长度 ≤1 的 token。"""
    return [w for w in jieba.lcut(text) if len(w.strip()) > 1]