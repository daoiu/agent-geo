"""Task 13 evals/runner.py --compare 双跑 react_loop + langgraph。

mock 两条路径返回固定 SSE chunks,验证 compare 逻辑产出 diff 报告。
"""
import json

import pytest

from evals.runner import compare_evals, _rouge_l


def _mk_sse(events):
    """Helper: 把 events list 转 bytes SSE (1 json per line)。"""
    out = []
    for ev in events:
        out.append((json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8"))
    return out


@pytest.mark.asyncio
async def test_rouge_l_identical_returns_one():
    assert _rouge_l("hello world", "hello world") == 1.0


@pytest.mark.asyncio
async def test_rouge_l_disjoint_returns_zero():
    assert _rouge_l("foo bar", "baz qux") == 0.0


@pytest.mark.asyncio
async def test_compare_evals_with_mocked_runners(tmp_path, monkeypatch):
    """双跑相同 case,两条路径使用 stub 返回相同 SSE 时,compare_evals 应该全 1.0。"""
    from app.domain.agent import dispatch as dispatch_module

    # 构造相同的 react / lang SSE chunks
    common_events = [
        {"event": "assistant_message", "content": "stubbed text"},
        {"event": "tool_call_start", "tool_call_id": "tc1", "tool_name": "diagnose_brand", "arguments": {}},
        {"event": "tool_call_result", "tool_call_id": "tc1", "result": {"ok": True}},
        {"event": "turn_complete"},
    ]
    common_chunks = _mk_sse(common_events)

    async def fake_react(session_id, message):
        for c in common_chunks:
            yield c

    async def fake_lang(session_id, message):
        for c in common_chunks:
            yield c

    monkeypatch.setattr(dispatch_module, "_run_react_loop_turn", fake_react)
    monkeypatch.setattr(dispatch_module, "_run_langgraph_turn", fake_lang)

    cases = [{"session_id": "c1", "message": "诊断品牌"}]
    report = await compare_evals(cases, output_dir=tmp_path)

    assert report["overall_match"] == 1.0
    assert report["tool_call_match"] == 1.0
    assert report["handoff_match"] == 1.0
    assert report["sse_event_count_equal"] is True
    assert (tmp_path / "diff_report.md").exists()


@pytest.mark.asyncio
async def test_compare_evals_detects_text_divergence(tmp_path, monkeypatch):
    """两路径 tool_call / handoff 一致但 assistant text 不同时,overall_match < 1.0。"""
    from app.domain.agent import dispatch as dispatch_module

    react_events = [
        {"event": "assistant_message", "content": "alpha beta gamma"},
        {"event": "tool_call_start", "tool_call_id": "tc1", "tool_name": "diagnose_brand", "arguments": {}},
        {"event": "tool_call_result", "tool_call_id": "tc1", "result": {"ok": True}},
        {"event": "turn_complete"},
    ]
    lang_events = [
        {"event": "assistant_message", "content": "completely different output text"},
        {"event": "tool_call_start", "tool_call_id": "tc1", "tool_name": "diagnose_brand", "arguments": {}},
        {"event": "tool_call_result", "tool_call_id": "tc1", "result": {"ok": True}},
        {"event": "turn_complete"},
    ]

    async def fake_react(session_id, message):
        for c in _mk_sse(react_events):
            yield c

    async def fake_lang(session_id, message):
        for c in _mk_sse(lang_events):
            yield c

    monkeypatch.setattr(dispatch_module, "_run_react_loop_turn", fake_react)
    monkeypatch.setattr(dispatch_module, "_run_langgraph_turn", fake_lang)

    cases = [{"session_id": "c1", "message": "诊断品牌"}]
    report = await compare_evals(cases, output_dir=tmp_path)

    assert report["tool_call_match"] == 1.0  # 工具调用 schema 一致
    assert report["handoff_match"] == 1.0
    assert report["overall_match"] < 1.0  # text 不一致
