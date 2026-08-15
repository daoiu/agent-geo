"""handoff 协议数据契约测试。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.agent.handoff import (
    HandoffRequest,
    HandoffResult,
    SpecialistHandoffError,
)


def test_handoff_request_construction():
    """HandoffRequest 5 字段都能正确构造。"""
    req = HandoffRequest(
        handoff_id=str(uuid.uuid4()),
        specialist="content_writer",
        task_id="task-1",
        session_id="session-1",
        started_at=datetime.now(timezone.utc),
        timeout_seconds=300,
        payload={"kb_id": "kb-1", "brand": "Acme"},
    )
    assert req.specialist == "content_writer"
    assert req.timeout_seconds == 300
    assert req.payload["kb_id"] == "kb-1"


def test_handoff_result_success():
    """成功回包字段。"""
    res = HandoffResult(
        handoff_id="h-1",
        status="success",
        result={"article_id": "art-1"},
        error=None,
        duration_ms=1500,
        token_usage={"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
    )
    assert res.status == "success"
    assert res.error is None
    assert res.token_usage["total_tokens"] == 300


def test_handoff_result_failure_has_error():
    """失败回包必须有 error 字段。"""
    with pytest.raises(ValueError, match="error 不能为空"):
        HandoffResult(
            handoff_id="h-1",
            status="failed",
            result=None,
            error=None,  # 失败时必须填 error
            duration_ms=500,
            token_usage={},
        )


def test_specialist_handoff_error_carries_handoff_id():
    """SpecialistHandoffError 必须带 handoff_id,用于日志关联。"""
    err = SpecialistHandoffError("timeout", handoff_id="h-2")
    assert err.handoff_id == "h-2"
    assert "timeout" in str(err)
