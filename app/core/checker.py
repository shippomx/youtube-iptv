import httpx
from app.config import settings


async def check_stream(stream_url: str) -> str:
    """对流地址发送 HEAD 请求，返回 'ok' 或 'dead'。"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.head(
                stream_url, timeout=settings.health_check_timeout_seconds
            )
        return "ok" if response.status_code == 200 else "dead"
    except Exception:
        return "dead"
