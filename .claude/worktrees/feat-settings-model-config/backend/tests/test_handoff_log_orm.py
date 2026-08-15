"""HandoffLogORM 表结构 + 索引测试。"""
from __future__ import annotations

from app.models.orm import Base
from app.models.orm_v05 import HandoffLogORM


def test_handoff_log_orm_table_name():
    """表名必须是 handoff_log(小写下划线)。"""
    assert HandoffLogORM.__tablename__ == "handoff_log"


def test_handoff_log_orm_registered_in_base():
    """HandoffLogORM 必须注册到 Base.metadata,SQLAlchemy 才能建表。"""
    mapper_class_names = {m.class_.__name__ for m in Base.registry.mappers}
    assert "HandoffLogORM" in mapper_class_names


def test_handoff_log_orm_has_indexes():
    """specialist / started_at / status 字段必须有索引(成本 dashboard 聚合用)。"""
    table = HandoffLogORM.__table__
    indexed_columns = {col.name for col in table.columns if col.index}
    assert "specialist" in indexed_columns
    assert "started_at" in indexed_columns
    assert "status" in indexed_columns
