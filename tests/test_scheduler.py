from unittest.mock import AsyncMock, patch

import pytest

import app.core.scheduler as sched_module
from app.core.scheduler import _resolve_and_check
from app.db.models import Channel


@pytest.fixture
def channel_in_db(db_session):
    ch = Channel(
        name="TVBS",
        source_url="https://youtube.com/watch?v=aaa",
        enabled=True,
        status="unknown",
        fail_count=0,
    )
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)
    return ch


@pytest.fixture(autouse=True)
def patch_session_local(db_session, monkeypatch):
    """让 scheduler 使用 in-memory session，并 mock close() 为 no-op
    避免 _resolve_and_check 的 finally db.close() 关闭测试用 session。"""
    db_session.close = lambda: None  # no-op
    monkeypatch.setattr("app.core.scheduler.SessionLocal", lambda: db_session)
    # 重置 semaphore，避免跨测试 event loop 问题
    sched_module._semaphore = None


async def test_resolve_success_sets_ok(channel_in_db, db_session):
    """解析成功 + 健康检测通过 → status=ok, fail_count=0"""
    with (
        patch("app.core.scheduler.resolve_stream", new=AsyncMock(return_value="https://stream.m3u8")),
        patch("app.core.scheduler.check_stream", new=AsyncMock(return_value="ok")),
    ):
        await _resolve_and_check(channel_in_db.id)

    db_session.refresh(channel_in_db)
    assert channel_in_db.status == "ok"
    assert channel_in_db.stream_url == "https://stream.m3u8"
    assert channel_in_db.fail_count == 0
    assert channel_in_db.last_check is not None


async def test_resolve_failure_increments_fail_count(channel_in_db, db_session):
    """解析失败 → fail_count 递增，status 不变（未达阈值）"""
    with patch("app.core.scheduler.resolve_stream", new=AsyncMock(return_value=None)):
        await _resolve_and_check(channel_in_db.id)

    db_session.refresh(channel_in_db)
    assert channel_in_db.fail_count == 1
    assert channel_in_db.status != "dead"


async def test_resolve_failure_threshold_marks_dead(channel_in_db, db_session):
    """连续 3 次解析失败 → status=dead"""
    channel_in_db.fail_count = 2
    db_session.commit()

    with patch("app.core.scheduler.resolve_stream", new=AsyncMock(return_value=None)):
        await _resolve_and_check(channel_in_db.id)

    db_session.refresh(channel_in_db)
    assert channel_in_db.status == "dead"
    assert channel_in_db.fail_count == 3


async def test_resolve_success_after_dead_recovers(channel_in_db, db_session):
    """解析成功后 fail_count 归零，status 恢复 ok（即使之前是 dead）"""
    channel_in_db.status = "dead"
    channel_in_db.fail_count = 3
    db_session.commit()

    with (
        patch("app.core.scheduler.resolve_stream", new=AsyncMock(return_value="https://stream.m3u8")),
        patch("app.core.scheduler.check_stream", new=AsyncMock(return_value="ok")),
    ):
        await _resolve_and_check(channel_in_db.id)

    db_session.refresh(channel_in_db)
    assert channel_in_db.status == "ok"
    assert channel_in_db.fail_count == 0


async def test_disabled_channel_skipped(channel_in_db, db_session):
    """disabled 频道不执行解析"""
    channel_in_db.enabled = False
    db_session.commit()

    with patch("app.core.scheduler.resolve_stream", new=AsyncMock()) as mock_resolve:
        await _resolve_and_check(channel_in_db.id)

    mock_resolve.assert_not_called()
