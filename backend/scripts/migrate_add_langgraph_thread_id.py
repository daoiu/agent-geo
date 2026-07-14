"""一次性 SQL 迁移:补齐 agent_sessions.langgraph_thread_id 列,无 alembic 时备选。

使用方式:
    sqlite3 data/geo.db < migrate_add_langgraph_thread_id.sql
a 项目内 alembic 已就位则改用:
    alembic upgrade head
"""
from __future__ import annotations

import sqlite3


SQL = """
ALTER TABLE agent_sessions ADD COLUMN langgraph_thread_id TEXT;
"""


def main(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SQL)
    finally:
        conn.close()
    print(f"已添加 langgraph_thread_id 列到 {db_path}")


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "data/geo.db")
