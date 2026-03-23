from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from app.core.checker import check_stream


@pytest.mark.asyncio
async def test_check_stream_ok():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await check_stream("https://example.com/stream.m3u8")
    assert result == "ok"


@pytest.mark.asyncio
async def test_check_stream_dead_on_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(side_effect=Exception("timeout"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await check_stream("https://example.com/stream.m3u8")
    assert result == "dead"


@pytest.mark.asyncio
async def test_check_stream_dead_on_non_200():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await check_stream("https://example.com/stream.m3u8")
    assert result == "dead"
