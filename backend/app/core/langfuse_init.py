"""v0.6+ P1#18（Task 19）：Langfuse LLM 调用可视化接入。

设计：
- init_langfuse() — 从 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY env 读,
  缺失时静默 no-op（per handoff §应急方案）
- get_langfuse() — 单例获取,未初始化返回 None（供 LLMClient 优雅退化）
- reset_langfuse_for_test() — 测试 hook,清空缓存
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langfuse import Langfuse  # noqa: F401  # 模块级 import 以便 mock

if TYPE_CHECKING:
    pass


_LANGFUSE_CLIENT: "Langfuse | None" = None


def init_langfuse(
    *,
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str | None = None,
) -> bool:
    """初始化 Langfuse 客户端。

    Returns:
        True 表示已初始化,False 表示 key 缺失未初始化。

    行为：
    - 任何 key 缺失 → 静默返回 False,不抛
    - 已初始化时再调 → 幂等,返回 True 不重新构造
    """
    global _LANGFUSE_CLIENT
    if _LANGFUSE_CLIENT is not None:
        return True

    pk = public_key if public_key is not None else os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sk = secret_key if secret_key is not None else os.environ.get("LANGFUSE_SECRET_KEY", "")
    h = host if host is not None else os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not pk or not sk:
        return False

    _LANGFUSE_CLIENT = Langfuse(
        public_key=pk,
        secret_key=sk,
        host=h,
    )
    return True


def get_langfuse() -> "Langfuse | None":
    """获取 Langfuse 客户端单例。未初始化返回 None,供 LLMClient 优雅退化。"""
    return _LANGFUSE_CLIENT


def reset_langfuse_for_test() -> None:
    """测试 hook:清空客户端缓存。"""
    global _LANGFUSE_CLIENT
    _LANGFUSE_CLIENT = None