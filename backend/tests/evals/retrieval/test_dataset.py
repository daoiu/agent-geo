"""金标集 jsonl 读写 + GoldenItem dataclass 测试。TDD:Step 1 — 先写失败测试。"""
import pytest

from evals.retrieval.dataset import GoldenItem, load_golden_set, save_golden_set


def test_save_then_load_roundtrip(tmp_path):
    items = [
        GoldenItem(id="q1", kb_id="kb1", query="什么是 GEO?",
                   relevant_chunk_ids=["c1", "c2"], reference_answer="GEO 是…"),
    ]
    p = tmp_path / "golden.jsonl"
    save_golden_set(items, p)
    loaded = load_golden_set(p)
    assert loaded == items


def test_load_skips_blank_lines(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"id":"q1","kb_id":"kb1","query":"q","relevant_chunk_ids":["c1"],"reference_answer":"a"}\n\n',
        encoding="utf-8",
    )
    assert len(load_golden_set(p)) == 1


def test_load_missing_field_raises(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"id":"q1","query":"q"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_golden_set(p)