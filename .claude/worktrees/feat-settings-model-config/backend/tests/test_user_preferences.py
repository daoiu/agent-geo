"""P2#46（Task 38）: 用户偏好学习测试。

目标:
- UserPreferences 数据类(风格/默认字数/行业/自定义关键词)
- 持久化到 JSON 文件(get/set/load/save)
- prefs_to_prompt(prefs) 返回 prompt 片段,影响 LLM 行为
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_user_preferences_dataclass_roundtrip():
    """UserPreferences 必须能 round-trip dict。"""
    from app.core.preferences import UserPreferences

    p = UserPreferences(
        user_id="u-1",
        response_style="concise",
        default_target_length=500,
        industry_preference="消费电子",
        custom_keywords=["AI", "大模型"],
        always_mention=["安全"],
        never_mention=["竞品X"],
    )
    d = p.to_dict()
    p2 = UserPreferences.from_dict(d)
    assert p2.user_id == "u-1"
    assert p2.response_style == "concise"
    assert p2.default_target_length == 500
    assert p2.always_mention == ["安全"]


def test_user_preferences_default_values():
    """UserPreferences 默认值合理。"""
    from app.core.preferences import UserPreferences

    p = UserPreferences(user_id="u-new")
    assert p.response_style == "balanced"  # 默认平衡风格
    assert p.default_target_length == 1500  # 与 Settings 一致
    assert p.custom_keywords == []
    assert p.always_mention == []
    assert p.never_mention == []


def test_prefs_store_persists_to_file(tmp_path: Path):
    """PreferencesStore 必须能持久化到 JSON 文件。"""
    from app.core.preferences import PreferencesStore, UserPreferences

    store_path = tmp_path / "prefs.json"
    store = PreferencesStore(path=store_path)
    store.save(UserPreferences(user_id="u-1", response_style="concise"))

    assert store_path.exists()
    # 新 store 从同一路径加载
    store2 = PreferencesStore(path=store_path)
    p = store2.get("u-1")
    assert p is not None
    assert p.response_style == "concise"


def test_prefs_store_get_missing_returns_none(tmp_path: Path):
    """不存在的 user_id 应返回 None 不抛。"""
    from app.core.preferences import PreferencesStore

    store = PreferencesStore(path=tmp_path / "prefs.json")
    assert store.get("nonexistent") is None


def test_prefs_store_update_existing(tmp_path: Path):
    """update 应覆盖已有 user 的 prefs(部分字段或全字段)。"""
    from app.core.preferences import PreferencesStore, UserPreferences

    store = PreferencesStore(path=tmp_path / "prefs.json")
    store.save(UserPreferences(user_id="u-1", response_style="balanced"))
    store.update("u-1", response_style="concise", default_target_length=800)
    p = store.get("u-1")
    assert p.response_style == "concise"
    assert p.default_target_length == 800


def test_prefs_to_prompt_includes_style():
    """prefs_to_prompt 必须把 response_style 转成 prompt 指令。"""
    from app.core.preferences import UserPreferences, prefs_to_prompt

    p = UserPreferences(user_id="u-1", response_style="concise")
    prompt = prefs_to_prompt(p)
    assert "concise" in prompt.lower() or "简洁" in prompt


def test_prefs_to_prompt_includes_target_length():
    """prefs_to_prompt 应含 default_target_length。"""
    from app.core.preferences import UserPreferences, prefs_to_prompt

    p = UserPreferences(user_id="u-1", default_target_length=500)
    prompt = prefs_to_prompt(p)
    assert "500" in prompt


def test_prefs_to_prompt_includes_always_never_mention():
    """prefs_to_prompt 应含 always_mention / never_mention 指令。"""
    from app.core.preferences import UserPreferences, prefs_to_prompt

    p = UserPreferences(
        user_id="u-1",
        always_mention=["安全", "合规"],
        never_mention=["竞品X"],
    )
    prompt = prefs_to_prompt(p)
    assert "安全" in prompt
    assert "合规" in prompt
    assert "竞品X" in prompt


def test_prefs_to_prompt_handles_empty():
    """空 prefs 不应崩,返回空字符串。"""
    from app.core.preferences import UserPreferences, prefs_to_prompt

    p = UserPreferences(user_id="u-1")
    prompt = prefs_to_prompt(p)
    # 应是字符串(可能为空或含默认值说明)
    assert isinstance(prompt, str)


def test_prefs_learn_from_correction(tmp_path: Path):
    """prefs 应能从用户纠正(显式 approve/reject + reason)中学习。"""
    from app.core.preferences import PreferencesStore, UserPreferences

    store = PreferencesStore(path=tmp_path / "learn.json")
    # 初始无偏好
    assert store.get("u-1") is None
    # 用户 reject + reason="文章太长" → 学习: default_target_length 缩减
    store.learn_from_correction(
        "u-1",
        action="reject",
        reason="文章太长,建议 500 字",
    )
    p = store.get("u-1")
    assert p is not None
    # 应提取出 default_target_length=500
    assert p.default_target_length == 500


def test_prefs_learn_no_op_when_no_signal(tmp_path: Path):
    """无信号时不应写入 prefs。"""
    from app.core.preferences import PreferencesStore

    store = PreferencesStore(path=tmp_path / "noop.json")
    store.learn_from_correction("u-1", action="approve", reason=None)
    # 无 prefs 时返回 None
    assert store.get("u-1") is None