import asyncio
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.core.checker import check_stream
from app.core.stream import resolve_stream
from app.db.database import SessionLocal
from app.db.models import Channel

# 全局 Semaphore，手动刷新与调度器共享
_semaphore: asyncio.Semaphore | None = None


def get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_resolves)
    return _semaphore


async def _resolve_and_check(channel_id: int) -> None:
    """解析单个频道的流地址并做健康检测，结果写回数据库。"""
    async with get_semaphore():
        db = SessionLocal()
        try:
            ch = db.get(Channel, channel_id)
            if not ch or not ch.enabled:
                return

            stream_url = await resolve_stream(
                ch.source_url, timeout=settings.resolve_timeout_seconds
            )

            if stream_url:
                status = await check_stream(stream_url)
                ch.stream_url = stream_url
                ch.fail_count = 0
                ch.status = status
            else:
                ch.fail_count = (ch.fail_count or 0) + 1
                if ch.fail_count >= settings.fail_threshold:
                    ch.status = "dead"
                # 保留旧 stream_url

            ch.last_check = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()


async def refresh_all_channels() -> None:
    """并发刷新所有启用频道（供调度器和 POST /channels/refresh-all 调用）。"""
    db = SessionLocal()
    try:
        ids = [ch.id for ch in db.query(Channel).filter(Channel.enabled == True).all()]
    finally:
        db.close()

    await asyncio.gather(*[_resolve_and_check(ch_id) for ch_id in ids])


async def refresh_single_channel(channel_id: int) -> None:
    """刷新单个频道（供 POST /channels/{id}/refresh 调用）。"""
    await _resolve_and_check(channel_id)


def create_scheduler() -> AsyncIOScheduler:
    """创建并配置 APScheduler，不自动启动。"""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        refresh_all_channels,
        trigger="interval",
        minutes=settings.refresh_interval_minutes,
        id="refresh_all",
        replace_existing=True,
    )
    return scheduler
