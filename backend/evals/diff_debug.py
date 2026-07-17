"""T9 调试:打印单 case 的 react_loop vs langgraph 完整 SSE 字节流。"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
from evals.runner import compare_evals, _collect_sse, _rouge_l
from evals.cases import EVAL_CASES

# 取 1 个 case,直接 compare
case = {
    "session_id": f"debug-{hash(EVAL_CASES[0].query) & 0xffffff:06x}",
    "message": EVAL_CASES[0].query,
}

# 复用 compare_evals 的 setup
import os
import tempfile
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.models.orm import Base
from app.repositories.agent_repo import AgentRepository
from app.domain.agent.dispatch import _run_react_loop_turn, _run_langgraph_turn

fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(fd)
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
from app.models import orm as _orm_v01  # noqa
from app.models import orm_v04 as _orm_v04  # noqa
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
factory = async_sessionmaker(engine, expire_on_commit=False)
import app.core.db
app.core.db._session_factory = factory
async with factory() as session:
    await AgentRepository(session).create_session(title=f"dbg-{case['session_id']}")


async def main():
    print(f"=== Case: {case['message'][:50]}... ===\n")
    react = await _collect_sse(_run_react_loop_turn, case["session_id"], case["message"])
    lang = await _collect_sse(_run_langgraph_turn, case["session_id"], case["message"])

    print(f"--- REACT_LOOP ({len(react)} events) ---")
    for e in react:
        evt = e.get("event")
        if evt == "assistant_message":
            print(f"  [{evt}] {e.get('content', '')[:80]}")
        else:
            print(f"  [{evt}] {json.dumps(e, ensure_ascii=False)[:100]}")

    print(f"\n--- LANGGRAPH ({len(lang)} events) ---")
    for e in lang:
        evt = e.get("event")
        if evt == "assistant_message":
            print(f"  [{evt}] {e.get('content', '')[:80]}")
        else:
            print(f"  [{evt}] {json.dumps(e, ensure_ascii=False)[:100]}")

    react_text = "".join(e.get("content", "") for e in react if e.get("event") == "assistant_message")
    lang_text = "".join(e.get("content", "") for e in lang if e.get("event") == "assistant_message")
    print(f"\nROUGE-L: {_rouge_l(react_text, lang_text):.3f}")

asyncio.run(main())