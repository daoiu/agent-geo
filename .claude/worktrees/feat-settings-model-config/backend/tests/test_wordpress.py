"""Tests for WordPress REST API client."""
import pytest
import respx
from httpx import Response

from app.domain.publisher.wordpress import PublishError, WordPressClient


@pytest.fixture
def client() -> WordPressClient:
    return WordPressClient(
        site_url="https://example.com",
        username="admin",
        app_password="abcd efgh ijkl mnop qrst uvwx",
        timeout=5.0,
    )


class TestTestConnection:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_user_info_on_success(self, client: WordPressClient) -> None:
        respx.get("https://example.com/wp-json/wp/v2/users/me").mock(
            return_value=Response(200, json={"id": 1, "name": "Admin", "slug": "admin"})
        )
        info = await client.test_connection()
        assert info["name"] == "Admin"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_401(self, client: WordPressClient) -> None:
        respx.get("https://example.com/wp-json/wp/v2/users/me").mock(
            return_value=Response(401, json={"code": "rest_unauthorized", "message": "Unauthorized"})
        )
        with pytest.raises(PublishError, match="认证失败"):
            await client.test_connection()

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_403(self, client: WordPressClient) -> None:
        respx.get("https://example.com/wp-json/wp/v2/users/me").mock(
            return_value=Response(403, json={"code": "forbidden"})
        )
        with pytest.raises(PublishError, match="权限不足"):
            await client.test_connection()

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_404(self, client: WordPressClient) -> None:
        respx.get("https://example.com/wp-json/wp/v2/users/me").mock(
            return_value=Response(404, json={"code": "rest_no_route"})
        )
        with pytest.raises(PublishError, match="URL 错误"):
            await client.test_connection()


class TestCreatePost:
    @pytest.mark.asyncio
    @respx.mock
    async def test_creates_post_and_returns_id_and_link(self, client: WordPressClient) -> None:
        respx.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=Response(
                201,
                json={"id": 42, "link": "https://example.com/?p=42"},
            )
        )
        result = await client.create_post(title="测试文章", content="<p>内容</p>")
        assert result["id"] == 42
        assert result["link"] == "https://example.com/?p=42"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_500(self, client: WordPressClient) -> None:
        respx.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=Response(500, text="Internal Server Error")
        )
        with pytest.raises(PublishError, match="500"):
            await client.create_post(title="X", content="Y")

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_400(self, client: WordPressClient) -> None:
        respx.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=Response(400, json={"code": "invalid_param", "message": "bad title"})
        )
        with pytest.raises(PublishError, match="400"):
            await client.create_post(title="", content="X")
