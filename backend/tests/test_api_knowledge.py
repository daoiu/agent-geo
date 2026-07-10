"""Integration tests for knowledge base API."""
from fastapi.testclient import TestClient


def test_create_kb(client: TestClient) -> None:
    resp = client.post(
        "/api/knowledge",
        json={"name": "测试 KB", "description": "描述"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["name"] == "测试 KB"


def test_list_kbs(client: TestClient) -> None:
    client.post("/api/knowledge", json={"name": "A"})
    client.post("/api/knowledge", json={"name": "B"})
    resp = client.get("/api/knowledge")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_kb_with_documents(client: TestClient) -> None:
    create = client.post("/api/knowledge", json={"name": "X"})
    kb_id = create.json()["id"]
    resp = client.get(f"/api/knowledge/{kb_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "X"
    assert "documents" in body
    assert body["documents"] == []


def test_get_kb_404(client: TestClient) -> None:
    resp = client.get("/api/knowledge/nonexistent-id")
    assert resp.status_code == 404


def test_create_kb_validates_name(client: TestClient) -> None:
    resp = client.post("/api/knowledge", json={"name": ""})
    assert resp.status_code == 422


def test_search_chunks(client: TestClient) -> None:
    import asyncio
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.core.db import get_session_factory

    factory = get_session_factory()

    async def _setup():
        async with factory() as s:
            repo = KnowledgeRepository(s)
            kb = await repo.create_kb(name="KB")
            doc = await repo.add_document(
                kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
                file_type="txt", file_size=100,
            )
            await repo.add_chunks(
                doc_id=doc.id, kb_id=kb.id,
                chunks=[
                    {"chunk_index": 0, "content": "小米手机性能优秀", "content_length": 8},
                    {"chunk_index": 1, "content": "华为手机", "content_length": 4},
                ],
            )
            return kb.id

    kb_id = asyncio.run(_setup())

    resp = client.get(f"/api/knowledge/{kb_id}/chunks?q=小米&limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["chunks"]) == 1
    assert "小米" in body["chunks"][0]["content"]


def test_delete_kb(client: TestClient) -> None:
    create = client.post("/api/knowledge", json={"name": "Del"})
    kb_id = create.json()["id"]
    resp = client.delete(f"/api/knowledge/{kb_id}")
    assert resp.status_code == 204
    get_resp = client.get(f"/api/knowledge/{kb_id}")
    assert get_resp.status_code == 404


def test_upload_document(client: TestClient) -> None:
    from tests.conftest import PROJECT_ROOT
    fixture = PROJECT_ROOT / "tests" / "fixtures" / "sample.txt"

    create = client.post("/api/knowledge", json={"name": "UploadKB"})
    kb_id = create.json()["id"]

    with open(fixture, "rb") as f:
        resp = client.post(
            f"/api/knowledge/{kb_id}/documents",
            files={"file": ("sample.txt", f, "text/plain")},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "sample.txt"
    assert body["file_type"] == "txt"
    assert body["parse_status"] in ("pending", "success")


def test_upload_rejects_unsupported_type(client: TestClient, tmp_path) -> None:
    create = client.post("/api/knowledge", json={"name": "TypeKB"})
    kb_id = create.json()["id"]

    bad = tmp_path / "bad.exe"
    bad.write_bytes(b"MZ")

    with open(bad, "rb") as f:
        resp = client.post(
            f"/api/knowledge/{kb_id}/documents",
            files={"file": ("bad.exe", f, "application/octet-stream")},
        )
    assert resp.status_code == 415


def test_full_v02_flow_with_mocked_workers(client: TestClient) -> None:
    """Full v0.2 flow: create KB → upload doc → create task → articles → review.

    Worker behavior is covered by unit tests; here we exercise the
    full API surface (KB → task → article → review) by directly
    populating the DB via repositories (mimicking what the workers
    would do post-generation).
    """
    import asyncio
    from app.core.db import get_session_factory
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.repositories.task_repo import TaskRepository

    # 1. Create KB
    kb = client.post("/api/knowledge", json={"name": "E2E KB"}).json()

    # 2. Upload doc (use real parser worker)
    from tests.conftest import PROJECT_ROOT
    from unittest.mock import patch
    with patch("app.api.knowledge.schedule_parse") as mock_parse:
        mock_parse.return_value = None
        with open(PROJECT_ROOT / "tests" / "fixtures" / "sample.txt", "rb") as f:
            doc = client.post(
                f"/api/knowledge/{kb['id']}/documents",
                files={"file": ("sample.txt", f, "text/plain")},
            ).json()
        assert doc["filename"] == "sample.txt"

    # 3. Manually populate chunks + create task + populate articles (simulating worker)
    async def _populate():
        async with get_session_factory()() as s:
            krepo = KnowledgeRepository(s)
            trepo = TaskRepository(s)

            # Mark document parsed + add chunks
            await krepo.update_document_status(
                doc["id"], status="success", chunk_count=2
            )
            await krepo.add_chunks(
                doc_id=doc["id"], kb_id=kb["id"],
                chunks=[
                    {"chunk_index": 0, "content": "小米手机", "content_length": 4},
                    {"chunk_index": 1, "content": "性能优秀", "content_length": 4},
                ],
            )

    asyncio.run(_populate())

    # 4. Create task via API (mock worker so it doesn't run)
    with patch("app.api.tasks.schedule_task") as mock_task:
        mock_task.return_value = None
        task = client.post("/api/tasks", json={
            "name": "E2E Task",
            "kb_id": kb["id"],
            "brand": "TestBrand",
            "topic": "足够长的主题",
            "article_count": 2,
            "style": "neutral",
        }).json()
        assert task["status"] == "pending"

    # 5. Manually create 2 articles via repo (simulating worker output)
    async def _seed_articles():
        async with get_session_factory()() as s:
            trepo = TaskRepository(s)
            for i in range(2):
                a = await trepo.create_article(task["id"], index=i)
                await trepo.update_article(
                    a.id, title=f"文章 {i + 1}", content="# 内容",
                    content_length=4, cited_chunks=[],
                )
            await trepo.update_task_status(
                task["id"], status="completed", progress=100
            )

    asyncio.run(_seed_articles())

    # 6. Verify task is completed with 2 articles
    t = client.get(f"/api/tasks/{task['id']}").json()
    assert t["status"] == "completed"
    assert len(t["articles"]) == 2

    # 7. Approve first article
    a1_id = t["articles"][0]["id"]
    approved = client.post(f"/api/reviews/{a1_id}/approve", json={}).json()
    assert approved["review_status"] == "approved"

    # 8. Verify it's now in approved queue
    approved_list = client.get("/api/reviews?status=approved").json()
    assert any(a["id"] == a1_id for a in approved_list)
