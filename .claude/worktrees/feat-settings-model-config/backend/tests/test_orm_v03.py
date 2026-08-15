"""Tests for v0.3 ORM models."""
import json
from datetime import datetime, timezone

import pytest

from app.models.orm_v03 import (
    MentionSnapshotORM,
    MonitorTaskORM,
    PublisherConfigORM,
    PublishJobORM,
)


@pytest.mark.asyncio
async def test_publisher_config_orm(db_session) -> None:
    p = PublisherConfigORM(
        id="pc1", name="主站", site_url="https://example.com",
        username="admin", app_password_encrypted="encrypted-blob", is_default=0,
    )
    db_session.add(p)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(PublisherConfigORM).where(PublisherConfigORM.id == "pc1")
    )
    fetched = result.scalar_one()
    assert fetched.name == "主站"


@pytest.mark.asyncio
async def test_publish_job_orm(db_session) -> None:
    # Need a parent article from v0.2 + parent publisher config from v0.3.
    # Follow v0.2 test pattern: commit parents before inserting child (FK ordering).
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1",
        topic="X", article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, pc])
    await db_session.commit()
    db_session.add(article)
    await db_session.commit()

    job = PublishJobORM(
        id="pj1", article_id="a1", config_id="pc1", status="pending",
    )
    db_session.add(job)
    await db_session.commit()

    assert job.status == "pending"
    assert job.remote_post_id is None


@pytest.mark.asyncio
async def test_monitor_task_orm(db_session) -> None:
    m = MonitorTaskORM(
        id="m1", name="监测小米", brand="小米", industry="手机",
        target_questions=json.dumps(["q1", "q2"], ensure_ascii=False),
        frequency="daily", providers=json.dumps(["deepseek"]),
        change_threshold=0.15, is_active=1,
    )
    db_session.add(m)
    await db_session.commit()
    assert m.is_active == 1
    assert m.frequency == "daily"


@pytest.mark.asyncio
async def test_mention_snapshot_orm(db_session) -> None:
    # Need a parent monitor task (FK with CASCADE)
    parent = MonitorTaskORM(
        id="m1", name="监测", brand="B", industry="I",
        target_questions=json.dumps(["q"]),
        frequency="daily", providers=json.dumps(["deepseek"]),
    )
    db_session.add(parent)
    await db_session.commit()

    snap = MentionSnapshotORM(
        id="s1", monitor_task_id="m1",
        run_at=datetime.now(timezone.utc),
        mention_rate=0.6, mention_count=3, total_samples=5,
        avg_position=1.5, details=json.dumps([]),
    )
    db_session.add(snap)
    await db_session.commit()
    assert snap.mention_rate == 0.6
    assert snap.total_samples == 5
