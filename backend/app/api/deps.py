"""FastAPI 共享依赖(headers、auth、context)。

首个成员:`device_id_header`,读 `X-Device-Id` 请求头(UUID v4),
合法则透传,非法/缺失静默返回 None,不抛 422。
用作 L2 跨会话记忆(scope key)的来源。
"""
from __future__ import annotations

import uuid

from fastapi import Header


async def device_id_header(
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> str | None:
    """读前端发出的 `X-Device-Id` header,做 UUID 校验。

    设计选择:**静默 None** 而非抛 422:
    - L2 记忆允许匿名(无 device_id → fallback `anon:<session_id>`)
    - 任何前端 bug/中间件剥离 header 不应阻塞主路径
    - 仅信任合法 UUID 字符串以避免污染 scope 字段
    """
    if not x_device_id:
        return None
    try:
        uuid.UUID(x_device_id)
        return x_device_id
    except (ValueError, AttributeError):
        return None
