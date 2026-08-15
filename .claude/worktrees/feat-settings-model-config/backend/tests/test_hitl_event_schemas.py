"""P1#33（Task 34）: 多类 HITL 事件 schema 测试。

目标:
- 三类 HITL 事件各有 Pydantic 模型
- 模型可导出为 JSON Schema (供前端 / OpenAPI 文档)
- SSE 事件 payload 校验通过
- 字段命名稳定(kind/event/message_id/tool_name/arguments + kind-specific extras)
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError


def test_decision_event_payload_validates() -> None:
    """HumanConfirmationRequired 的 SSE payload 必须通过 DecisionRequiredEvent 校验。"""
    from app.domain.hitl_schemas import DecisionRequiredEvent

    payload = {
        "event": "human_confirmation_required",
        "kind": "decision",
        "message_id": "m-1",
        "tool_name": "generate_article",
        "arguments": {"title": "x", "target_length": 500},
    }
    evt = DecisionRequiredEvent(**payload)
    assert evt.kind == "decision"
    assert evt.tool_name == "generate_article"
    assert evt.arguments == {"title": "x", "target_length": 500}


def test_input_event_payload_validates() -> None:
    """InputRequired 的 SSE payload 必须通过 InputRequiredEvent 校验,含 input_schema + prompt。"""
    from app.domain.hitl_schemas import InputRequiredEvent

    payload = {
        "event": "input_required",
        "kind": "input",
        "message_id": "m-2",
        "tool_name": "search_local",
        "arguments": {"query": "天气"},
        "input_schema": {
            "fields": [
                {"name": "city", "type": "string", "required": True},
            ]
        },
        "prompt": "请告诉我哪个城市?",
    }
    evt = InputRequiredEvent(**payload)
    assert evt.kind == "input"
    assert evt.input_schema["fields"][0]["name"] == "city"
    assert evt.prompt == "请告诉我哪个城市?"


def test_progress_event_payload_validates() -> None:
    """ProgressConfirm 的 SSE payload 必须通过 ProgressConfirmEvent 校验,含 progress_pct + eta_seconds。"""
    from app.domain.hitl_schemas import ProgressConfirmEvent

    payload = {
        "event": "progress_confirm",
        "kind": "progress_confirm",
        "message_id": "m-3",
        "tool_name": "batch_generate",
        "arguments": {"task_id": "t-99"},
        "progress_pct": 42.5,
        "eta_seconds": 120,
    }
    evt = ProgressConfirmEvent(**payload)
    assert evt.progress_pct == 42.5
    assert evt.eta_seconds == 120


def test_decision_event_rejects_wrong_kind() -> None:
    """kind=input 的 payload 不能通过 DecisionRequiredEvent 校验。"""
    from app.domain.hitl_schemas import DecisionRequiredEvent

    bad = {
        "event": "human_confirmation_required",
        "kind": "input",  # 错的 kind
        "message_id": "m-1",
        "tool_name": "x",
        "arguments": {},
    }
    with pytest.raises(ValidationError):
        DecisionRequiredEvent(**bad)


def test_input_event_requires_input_schema_and_prompt() -> None:
    """InputRequiredEvent 缺少 input_schema / prompt 应抛 ValidationError。"""
    from app.domain.hitl_schemas import InputRequiredEvent

    base = {
        "event": "input_required",
        "kind": "input",
        "message_id": "m-2",
        "tool_name": "search_local",
        "arguments": {},
    }
    # 缺 input_schema
    with pytest.raises(ValidationError):
        InputRequiredEvent(**base, prompt="p")
    # 缺 prompt
    with pytest.raises(ValidationError):
        InputRequiredEvent(**base, input_schema={"fields": []})


def test_progress_event_requires_progress_fields() -> None:
    """ProgressConfirmEvent 缺少 progress_pct / eta_seconds 应抛 ValidationError。"""
    from app.domain.hitl_schemas import ProgressConfirmEvent

    base = {
        "event": "progress_confirm",
        "kind": "progress_confirm",
        "message_id": "m-3",
        "tool_name": "batch_generate",
        "arguments": {},
    }
    with pytest.raises(ValidationError):
        ProgressConfirmEvent(**base)
    with pytest.raises(ValidationError):
        ProgressConfirmEvent(**base, progress_pct=10.0)
    with pytest.raises(ValidationError):
        ProgressConfirmEvent(**base, eta_seconds=5)


def test_hitl_event_kinds_are_stable() -> None:
    """kind / event 字段值必须稳定(防止破坏前端契约)。"""
    from app.domain.hitl_schemas import (
        DecisionRequiredEvent,
        InputRequiredEvent,
        ProgressConfirmEvent,
    )

    assert DecisionRequiredEvent.model_fields["kind"].default == "decision"
    assert DecisionRequiredEvent.model_fields["event"].default == "human_confirmation_required"
    assert InputRequiredEvent.model_fields["kind"].default == "input"
    assert InputRequiredEvent.model_fields["event"].default == "input_required"
    assert ProgressConfirmEvent.model_fields["kind"].default == "progress_confirm"
    assert ProgressConfirmEvent.model_fields["event"].default == "progress_confirm"


def test_schemas_export_json_schema() -> None:
    """所有 schema 必须能导出 JSON Schema(供前端 codegen)。"""
    from app.domain.hitl_schemas import (
        DecisionRequiredEvent,
        InputRequiredEvent,
        ProgressConfirmEvent,
    )

    for cls in (DecisionRequiredEvent, InputRequiredEvent, ProgressConfirmEvent):
        schema = cls.model_json_schema()
        # 必须能 JSON 序列化
        json_text = json.dumps(schema, ensure_ascii=False)
        assert "kind" in json_text
        assert "message_id" in json_text
        assert "tool_name" in json_text


def test_schemas_list_exports_all_three() -> None:
    """hitl_schemas 模块必须导出全部三类。"""
    from app.domain import hitl_schemas

    assert hasattr(hitl_schemas, "DecisionRequiredEvent")
    assert hasattr(hitl_schemas, "InputRequiredEvent")
    assert hasattr(hitl_schemas, "ProgressConfirmEvent")
    assert hasattr(hitl_schemas, "HITL_EVENT_SCHEMAS")  # 字典聚合


def test_hitl_event_schemas_dict_aggregates() -> None:
    """HITL_EVENT_SCHEMAS 必须按 kind 索引全部三类。"""
    from app.domain.hitl_schemas import HITL_EVENT_SCHEMAS

    assert "decision" in HITL_EVENT_SCHEMAS
    assert "input" in HITL_EVENT_SCHEMAS
    assert "progress_confirm" in HITL_EVENT_SCHEMAS
    # 每项都是 dict (Pydantic 类)
    for kind, schema_cls in HITL_EVENT_SCHEMAS.items():
        assert hasattr(schema_cls, "model_json_schema")