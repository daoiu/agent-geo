"""Tests for HumanConfirmationRequired exception (v0.4)."""
from __future__ import annotations

from app.domain.exceptions import DomainError, HumanConfirmationRequired


def test_human_confirmation_required_inherits_domain_error() -> None:
    """HumanConfirmationRequired is a DomainError."""
    err = HumanConfirmationRequired(
        message_id="m1", tool_name="generate_article", arguments={"foo": "bar"}
    )
    assert isinstance(err, DomainError)


def test_human_confirmation_required_carries_message_id() -> None:
    """message_id is preserved on the exception instance."""
    err = HumanConfirmationRequired(
        message_id="msg-123",
        tool_name="generate_article",
        arguments={},
    )
    assert err.message_id == "msg-123"


def test_human_confirmation_required_carries_tool_name() -> None:
    """tool_name is preserved on the exception instance."""
    err = HumanConfirmationRequired(
        message_id="m1", tool_name="generate_article", arguments={}
    )
    assert err.tool_name == "generate_article"


def test_human_confirmation_required_carries_arguments() -> None:
    """arguments dict is preserved on the exception instance."""
    args = {
        "kb_id": "kb1",
        "brand": "小米",
        "topic": "产品评测",
        "keywords": ["性能", "拍照"],
    }
    err = HumanConfirmationRequired(
        message_id="m1", tool_name="generate_article", arguments=args
    )
    assert err.arguments == args


def test_human_confirmation_required_message_contains_tool_name() -> None:
    """str(err) includes the tool_name for logs."""
    err = HumanConfirmationRequired(
        message_id="m1", tool_name="generate_article", arguments={}
    )
    assert "generate_article" in str(err)


def test_human_confirmation_required_message_contains_message_id() -> None:
    """str(err) includes the message_id for traceability."""
    err = HumanConfirmationRequired(
        message_id="msg-abc-123", tool_name="generate_article", arguments={}
    )
    assert "msg-abc-123" in str(err)