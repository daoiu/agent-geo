"""用户偏好学习(P2#46 / Task 38)。

简化设计(in-memory + JSON 文件持久化):
- UserPreferences: 偏好数据类
- PreferencesStore: 按 user_id 索引,持久化到 JSON
- prefs_to_prompt(prefs): 转成 prompt 片段,影响 LLM
- learn_from_correction: 从用户 reject + reason 自动学习

P2 范围内,文件级持久化足够。如需多用户/并发/审计,后续阶段可迁 ORM。
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class UserPreferences:
    """用户偏好。"""

    # 标记:这不是 pytest test class(防止 pytest 把它当 test 收集)
    __test__ = False

    user_id: str
    response_style: str = "balanced"  # concise | balanced | detailed | friendly | professional
    default_target_length: int = 1500
    industry_preference: str = ""
    custom_keywords: list[str] = field(default_factory=list)
    always_mention: list[str] = field(default_factory=list)
    never_mention: list[str] = field(default_factory=list)
    updated_at: str = ""  # ISO 时间

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UserPreferences":
        # 过滤未知字段(向前兼容)
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


class PreferencesStore:
    """文件持久化的 preferences store。

    线程安全(简单 lock)。如需多进程/分布式,后续阶段替换后端。
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        # RLock: update() 内会调 save(),save() 需要同一把锁;非可重入锁会死锁
        self._lock = threading.RLock()
        self._cache: dict[str, UserPreferences] = {}
        self._loaded = False

    def _load(self) -> None:
        """从文件加载到内存(首次访问触发)。"""
        if self._loaded:
            return
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._cache = {
                    k: UserPreferences.from_dict(v) for k, v in raw.items()
                }
            except (json.JSONDecodeError, KeyError, TypeError):
                self._cache = {}
        self._loaded = True

    def _flush(self) -> None:
        """内存写回文件。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {k: v.to_dict() for k, v in self._cache.items()}
        self.path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, user_id: str) -> UserPreferences | None:
        with self._lock:
            self._load()
            return self._cache.get(user_id)

    def save(self, prefs: UserPreferences) -> None:
        from datetime import datetime, timezone

        prefs.updated_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._load()
            self._cache[prefs.user_id] = prefs
            self._flush()

    def update(self, user_id: str, **fields: Any) -> UserPreferences:
        """部分字段更新。"""
        with self._lock:
            self._load()
            existing = self._cache.get(user_id) or UserPreferences(user_id=user_id)
            for k, v in fields.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            self.save(existing)
            return existing

    def learn_from_correction(
        self,
        user_id: str,
        action: str,
        reason: str | None = None,
    ) -> UserPreferences | None:
        """从用户纠正(reject + reason)学习偏好。

        启发式提取:
        - "太长/太短" → 调整 target_length(从 reason 抓数字)
        - "简洁/详细" → 调整 response_style
        - "行业X" → 调整 industry_preference

        无信号(approve 或 无 reason) → 不写入。
        """
        if action != "reject" or not reason:
            return None

        updates: dict[str, Any] = {}

        # 提取字数
        m = re.search(r"(\d{2,5})\s*字", reason)
        if m:
            n = int(m.group(1))
            if 100 <= n <= 10_000:
                updates["default_target_length"] = n

        # 提取风格
        if "简洁" in reason or "简短" in reason:
            updates["response_style"] = "concise"
        elif "详细" in reason or "展开" in reason:
            updates["response_style"] = "detailed"
        elif "友好" in reason or "亲切" in reason:
            updates["response_style"] = "friendly"

        # 提取行业
        m = re.search(r"行业[：:是]?\s*([一-龥A-Za-z0-9]+)", reason)
        if m:
            updates["industry_preference"] = m.group(1)

        if not updates:
            return None

        return self.update(user_id, **updates)


def prefs_to_prompt(prefs: UserPreferences) -> str:
    """把 UserPreferences 转成可注入 system prompt 的指令片段。"""
    lines: list[str] = []

    style_map = {
        "concise": "回答要简洁,直奔主题,不啰嗦。",
        "detailed": "回答要详细,展开解释,给出背景和例子。",
        "friendly": "回答语气要友好亲切,像朋友聊天。",
        "professional": "回答要专业严谨,使用专业术语。",
        "balanced": "",  # 默认风格,不额外指令
    }
    style_line = style_map.get(prefs.response_style, "")
    if style_line:
        lines.append(style_line)

    if prefs.default_target_length and prefs.default_target_length != 1500:
        lines.append(f"默认文章长度 {prefs.default_target_length} 字。")

    if prefs.industry_preference:
        lines.append(f"用户偏好行业: {prefs.industry_preference}。")

    if prefs.always_mention:
        lines.append(f"始终提及: {', '.join(prefs.always_mention)}。")
    if prefs.never_mention:
        lines.append(f"禁止提及: {', '.join(prefs.never_mention)}。")

    if prefs.custom_keywords:
        lines.append(f"用户关注关键词: {', '.join(prefs.custom_keywords)}。")

    return "\n".join(lines)


# 全局默认 store(单例)
_DEFAULT_STORE: PreferencesStore | None = None


def get_default_store() -> PreferencesStore:
    """获取默认 store(单例,data/user_prefs.json)。"""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        from app.core.config import get_settings

        settings = get_settings()
        # 复用 data/ 目录
        from pathlib import Path
        data_dir = Path(settings.database_url.replace("sqlite+aiosqlite:///", "")).parent
        _DEFAULT_STORE = PreferencesStore(path=data_dir / "user_prefs.json")
    return _DEFAULT_STORE


__all__ = [
    "UserPreferences",
    "PreferencesStore",
    "prefs_to_prompt",
    "get_default_store",
]