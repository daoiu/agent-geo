"""v0.6+ P1#19（Task 20）：trace_id 串联（contextvars）。

设计：
- contextvars 实现 trace_id 跨异步任务隔离(每个请求独立)
- new_trace_id() 生成 UUID4(每个 turn / 每个请求一个)
- set_trace_id / get_trace_id / clear_trace_id 操作 contextvar
- trace_id_processor 注入 structlog 日志,所有 log 事件自动带 trace_id
- 便于跨服务/跨日志追踪单次请求

使用模式：
    # 在 API 入口处
    tid = new_trace_id()
    set_trace_id(tid)
    yield  # 让请求处理执行
    clear_trace_id()

    # 业务代码中
    logger.info("processing", foo="bar")
    # 自动带 trace_id="xxx" 输出
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def new_trace_id() -> str:
    """生成新的 trace_id(UUID4 字符串)。"""
    return str(uuid.uuid4())


def set_trace_id(trace_id: str) -> None:
    """设置当前 contextvar 的 trace_id。"""
    _trace_id_var.set(trace_id)


def get_trace_id() -> str | None:
    """获取当前 contextvar 的 trace_id,未设置时返回 None。"""
    return _trace_id_var.get()


def clear_trace_id() -> None:
    """清空当前 contextvar 的 trace_id,恢复默认 None。"""
    _trace_id_var.set(None)


def trace_id_processor(logger: Any, method_name: str, event_dict: dict) -> dict:
    """structlog processor:把 trace_id 从 contextvar 注入 log 事件。

    未设置 trace_id 时注入 None（便于日志解析,不抛异常）。
    """
    event_dict["trace_id"] = get_trace_id()
    return event_dict