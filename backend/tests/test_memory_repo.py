"""MemoryRepository 测试 — CRUD + list_by_scope + replace_all_bulk。"""
import pytest


@pytest.mark.asyncio
async def test_create_and_get_by_id(db_session):
    from app.repositories.memory_repo import MemoryRepository

    repo = MemoryRepository(db_session)
    m = await repo.create(
        scope="device-1", name="x", description="d",
        type="user", body_md="body", session_id="s1",
    )
    assert m["id"]
    assert m["scope"] == "device-1"
    assert m["name"] == "x"

    fetched = await repo.get_by_id(m["id"])
    assert fetched is not None
    assert fetched["name"] == "x"
    assert fetched["body_md"] == "body"


@pytest.mark.asyncio
async def test_get_by_id_returns_none(db_session):
    from app.repositories.memory_repo import MemoryRepository

    repo = MemoryRepository(db_session)
    assert await repo.get_by_id("non-existent-id") is None


@pytest.mark.asyncio
async def test_get_by_name(db_session):
    from app.repositories.memory_repo import MemoryRepository

    repo = MemoryRepository(db_session)
    await repo.create(scope="d", name="foo", description="x", type="user", body_md="")
    found = await repo.get_by_name("d", "foo")
    assert found is not None
    assert found["name"] == "foo"

    missing = await repo.get_by_name("d", "bar")
    assert missing is None


@pytest.mark.asyncio
async def test_list_by_scope_filters(db_session):
    from app.repositories.memory_repo import MemoryRepository

    repo = MemoryRepository(db_session)
    await repo.create(scope="device-1", name="a", description="d1",
                      type="user", body_md="")
    await repo.create(scope="device-1", name="b", description="d2",
                      type="project", body_md="")
    await repo.create(scope="device-2", name="c", description="d3",
                      type="user", body_md="")

    rows = await repo.list_by_scope("device-1")
    assert {r["name"] for r in rows} == {"a", "b"}

    rows2 = await repo.list_by_scope("device-2")
    assert {r["name"] for r in rows2} == {"c"}


@pytest.mark.asyncio
async def test_count_by_scope(db_session):
    from app.repositories.memory_repo import MemoryRepository

    repo = MemoryRepository(db_session)
    for i in range(3):
        await repo.create(scope="d", name=f"m{i}", description="d",
                          type="user", body_md="")
    assert await repo.count_by_scope("d") == 3
    assert await repo.count_by_scope("other") == 0


@pytest.mark.asyncio
async def test_replace_all_bulk(db_session):
    """consolidate 用:删该 scope 全部,按 items 重建。"""
    from app.repositories.memory_repo import MemoryRepository

    repo = MemoryRepository(db_session)
    for i in range(5):
        await repo.create(scope="d", name=f"old{i}", description="d",
                          type="user", body_md="")

    new_items = [
        {"name": "newA", "type": "user", "description": "da", "body_md": ""},
        {"name": "newB", "type": "project", "description": "db", "body_md": ""},
    ]
    await repo.replace_all_bulk("d", new_items)

    rows = await repo.list_by_scope("d")
    assert {r["name"] for r in rows} == {"newA", "newB"}
    # 旧全部清空
    assert "old0" not in {r["name"] for r in rows}


@pytest.mark.asyncio
async def test_replace_all_bulk_only_affects_target_scope(db_session):
    from app.repositories.memory_repo import MemoryRepository

    repo = MemoryRepository(db_session)
    await repo.create(scope="d1", name="keep-me",
                      description="x", type="user", body_md="")
    await repo.create(scope="d2", name="wipe-me",
                      description="y", type="user", body_md="")

    await repo.replace_all_bulk("d2", [])
    rows1 = await repo.list_by_scope("d1")
    rows2 = await repo.list_by_scope("d2")
    assert {r["name"] for r in rows1} == {"keep-me"}
    assert rows2 == []
