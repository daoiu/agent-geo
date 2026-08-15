"""device_id_header 依赖:UUID 校验、非法/缺失静默 None。"""
import pytest

from app.api.deps import device_id_header


VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_valid_uuid_passes_through():
    assert await device_id_header(VALID_UUID) == VALID_UUID


@pytest.mark.asyncio
async def test_invalid_uuid_returns_none():
    """非 UUID 字符串返回 None,不抛异常。"""
    assert await device_id_header("not-a-uuid") is None


@pytest.mark.asyncio
async def test_empty_string_returns_none():
    assert await device_id_header("") is None


@pytest.mark.asyncio
async def test_missing_header_returns_none():
    """header 完全没传(FastAPI 不会调用默认值之外的钩子),对应 None。"""
    assert await device_id_header(None) is None


@pytest.mark.asyncio
async def test_uuid_with_extra_chars_returns_none():
    assert await device_id_header(f"{VALID_UUID}junk") is None
