"""P1#31（Task 32）: HITL 多场景测试。

目标:
- HumanConfirmationRequired 保留(向后兼容)
- 新增 InputRequired: 用户补充输入/参数
- 新增 ProgressConfirm: 长任务中途确认
- 三类有 kind 区分 + 各自 extra 字段
- react_loop 能识别并 yield 不同 SSE 事件
"""
from __future__ import annotations

import pytest


def test_human_confirmation_required_backward_compat():
    """HumanConfirmationRequired 保持原有构造函数签名(message_id/tool_name/arguments)。"""
    from app.domain.exceptions import HumanConfirmationRequired

    exc = HumanConfirmationRequired(
        message_id="m-1", tool_name="generate_article", arguments={"x": 1}
    )
    assert exc.message_id == "m-1"
    assert exc.tool_name == "generate_article"
    assert exc.arguments == {"x": 1}
    assert exc.kind == "decision"


def test_human_confirmation_base_is_base_of_all_kinds():
    """HumanConfirmationBase 是三种 HITL 的公共基类。"""
    from app.domain.exceptions import (
        HumanConfirmationBase,
        HumanConfirmationRequired,
        InputRequired,
        ProgressConfirm,
    )

    for cls in (HumanConfirmationRequired, InputRequired, ProgressConfirm):
        assert issubclass(cls, HumanConfirmationBase), (
            f"{cls.__name__} must subclass HumanConfirmationBase"
        )


def test_three_kinds_have_distinct_discriminators():
    """三类 HITL 必须有不同 kind 值(读取类属性,无需实例化)。"""
    from app.domain.exceptions import (
        HumanConfirmationRequired,
        InputRequired,
        ProgressConfirm,
    )

    kinds = {
        HumanConfirmationRequired.kind,
        InputRequired.kind,
        ProgressConfirm.kind,
    }
    assert len(kinds) == 3, f"kind discriminators must be unique; got {kinds}"


def test_input_required_carries_input_schema():
    """InputRequired 必须携带 input_schema(描述需要哪些字段)。"""
    from app.domain.exceptions import InputRequired

    schema = {"fields": [{"name": "city", "type": "string", "required": True}]}
    exc = InputRequired(
        message_id="m-2",
        tool_name="search_local",
        arguments={"query": "天气"},
        input_schema=schema,
        prompt="请补充城市名",
    )
    assert exc.kind == "input"
    assert exc.input_schema == schema
    assert exc.prompt == "请补充城市名"
    assert exc.tool_name == "search_local"


def test_progress_confirm_carries_progress_info():
    """ProgressConfirm 必须携带 progress_pct + eta_seconds。"""
    from app.domain.exceptions import ProgressConfirm

    exc = ProgressConfirm(
        message_id="m-3",
        tool_name="long_running_task",
        arguments={"task_id": "t-99"},
        progress_pct=42.5,
        eta_seconds=120,
    )
    assert exc.kind == "progress_confirm"
    assert exc.progress_pct == 42.5
    assert exc.eta_seconds == 120


def test_hitl_exceptions_are_domain_errors():
    """所有 HITL 异常必须继承 DomainError。"""
    from app.domain.exceptions import (
        DomainError,
        HumanConfirmationRequired,
        InputRequired,
        ProgressConfirm,
    )

    for cls in (HumanConfirmationRequired, InputRequired, ProgressConfirm):
        assert issubclass(cls, DomainError), (
            f"{cls.__name__} must subclass DomainError"
        )


def test_hitl_exceptions_are_caught_by_base_class_handler():
    """react_loop 用 isinstance(exc, HumanConfirmationBase) 能捕获全部三类。"""
    from app.domain.exceptions import (
        HumanConfirmationBase,
        HumanConfirmationRequired,
        InputRequired,
        ProgressConfirm,
    )

    samples = [
        HumanConfirmationRequired("m1", "t1", {}),
        InputRequired("m2", "t2", {}, input_schema={"x": 1}, prompt="p"),
        ProgressConfirm("m3", "t3", {}, progress_pct=10.0, eta_seconds=5),
    ]
    for exc in samples:
        assert isinstance(exc, HumanConfirmationBase)


def test_hitl_kind_serialization_roundtrip():
    """kind 字段可被 JSON 序列化(用于 SSE 事件)。"""
    import json
    from app.domain.exceptions import InputRequired, ProgressConfirm

    exc = InputRequired(
        "m-2", "search_local", {}, input_schema={"x": 1}, prompt="p"
    )
    # JSON 序列化 kind + message_id + tool_name + arguments
    payload = {
        "kind": exc.kind,
        "message_id": exc.message_id,
        "tool_name": exc.tool_name,
        "arguments": exc.arguments,
        "input_schema": exc.input_schema,
        "prompt": exc.prompt,
    }
    text = json.dumps(payload, ensure_ascii=False)
    parsed = json.loads(text)
    assert parsed["kind"] == "input"
    assert parsed["input_schema"] == {"x": 1}


def test_hitl_event_kinds_for_sse():
    """SSE 事件应使用 kind 区分(避免单一 confirmation_required 类型)。"""
    from app.domain.exceptions import (
        HumanConfirmationRequired,
        InputRequired,
        ProgressConfirm,
    )

    # 使用类属性 .kind (无需实例化)
    expected_event_kinds = {
        HumanConfirmationRequired.kind: "human_confirmation_required",
        InputRequired.kind: "input_required",
        ProgressConfirm.kind: "progress_confirm",
    }
    assert expected_event_kinds["decision"] == "human_confirmation_required"
    assert expected_event_kinds["input"] == "input_required"
    assert expected_event_kinds["progress_confirm"] == "progress_confirm"