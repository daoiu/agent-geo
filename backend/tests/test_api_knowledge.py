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
