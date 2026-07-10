"""ORM models for the GEO Agent (v0.1 base + v0.2 knowledge/task + v0.3 publisher/monitor).

Import all ORM modules here so SQLAlchemy registers every table in
``Base.metadata``. Required because v0.3 tables (publish_jobs, mention_snapshots)
have ForeignKey references to v0.2 tables (articles, monitor_tasks) — without
this, importing ``app.models.orm_v03`` in isolation raises
``NoReferencedTableError`` because the referenced table hasn't been registered yet.
"""
from app.models import orm  # noqa: F401  # v0.1: Base + reports
from app.models import orm_v02  # noqa: F401  # v0.2: knowledge_bases / tasks / articles
from app.models import orm_v03  # noqa: F401  # v0.3: publisher_configs / publish_jobs / monitor_tasks / mention_snapshots
