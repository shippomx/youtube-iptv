import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.core.stream import resolve_stream


@pytest.mark.asyncio
async def test_resolve_stream_success():
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(
        return_value=(b"https://example.com/stream.m3u8\n", b"")
    )
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await resolve_stream("https://youtube.com/watch?v=xxx")
    assert result == "https://example.com/stream.m3u8"


@pytest.mark.asyncio
async def test_resolve_stream_empty_output():
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await resolve_stream("https://youtube.com/watch?v=xxx")
    assert result is None


@pytest.mark.asyncio
async def test_resolve_stream_timeout():
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_proc.kill = MagicMock()
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await resolve_stream("https://youtube.com/watch?v=xxx", timeout=1)
    assert result is None
    mock_proc.kill.assert_called_once()
