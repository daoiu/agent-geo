"""WordPress REST API client (Application Passwords auth)."""
from __future__ import annotations

from typing import Any

import httpx

from app.domain.exceptions import PublishError

# Re-export so tests can do `from app.domain.publisher.wordpress import PublishError`.
__all__ = ["PublishError", "WordPressClient"]


class WordPressClient:
    """Async client for WordPress REST API v2."""

    def __init__(
        self,
        site_url: str,
        username: str,
        app_password: str,
        timeout: float = 30.0,
    ) -> None:
        self.site_url = site_url.rstrip("/")
        self.username = username
        self.app_password = app_password
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                auth=(self.username, self.app_password),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "WordPressClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def test_connection(self) -> dict[str, Any]:
        """Call /users/me to verify credentials. Returns user info on success."""
        client = self._get_client()
        try:
            resp = await client.get(f"{self.site_url}/wp-json/wp/v2/users/me")
        except httpx.TimeoutException as e:
            raise PublishError(f"请求超时：{e}") from e
        except httpx.HTTPError as e:
            raise PublishError(f"网络错误：{type(e).__name__}: {e}") from e

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401:
            raise PublishError("认证失败：用户名或 Application Password 错误")
        if resp.status_code == 403:
            raise PublishError("权限不足：用户没有访问权限")
        if resp.status_code == 404:
            raise PublishError("WordPress 站点 URL 错误或 REST API 未启用")
        raise PublishError(f"WordPress API 错误 {resp.status_code}: {resp.text[:200]}")

    async def create_post(self, title: str, content: str) -> dict[str, Any]:
        """Create a new post. Returns {"id": int, "link": str} on success."""
        client = self._get_client()
        try:
            resp = await client.post(
                f"{self.site_url}/wp-json/wp/v2/posts",
                json={
                    "title": title,
                    "content": content,
                    "status": "publish",
                },
            )
        except httpx.TimeoutException as e:
            raise PublishError(f"请求超时：{e}") from e
        except httpx.HTTPError as e:
            raise PublishError(f"网络错误：{type(e).__name__}: {e}") from e

        if resp.status_code == 201:
            return resp.json()
        if resp.status_code == 400:
            raise PublishError(f"请求参数错误 400：{resp.text[:200]}")
        if resp.status_code == 401:
            raise PublishError("认证失败：用户名或 Application Password 错误")
        if resp.status_code == 403:
            raise PublishError("权限不足：用户没有发布权限")
        if resp.status_code == 404:
            raise PublishError("WordPress 站点 URL 错误或 REST API 未启用")
        raise PublishError(
            f"WordPress API 错误 {resp.status_code}: {resp.text[:200]}"
        )
