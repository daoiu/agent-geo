"""金标数据集:GoldenItem + jsonl 读写。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_REQUIRED = ("id", "kb_id", "query", "relevant_chunk_ids", "reference_answer")


@dataclass
class GoldenItem:
    id: str
    kb_id: str
    query: str
    relevant_chunk_ids: list[str] = field(default_factory=list)
    reference_answer: str = ""


def load_golden_set(path: str | Path) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        missing = [k for k in _REQUIRED if k not in obj]
        if missing:
            raise ValueError(f"金标条目缺字段 {missing}: {line[:80]}")
        items.append(
            GoldenItem(
                id=obj["id"],
                kb_id=obj["kb_id"],
                query=obj["query"],
                relevant_chunk_ids=list(obj["relevant_chunk_ids"]),
                reference_answer=obj["reference_answer"],
            )
        )
    return items


def save_golden_set(items: list[GoldenItem], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")