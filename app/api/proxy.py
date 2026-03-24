import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.stream import resolve_stream
from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(tags=["proxy"])


async def _stream_ffmpeg(stream_url: str):
    """启动 ffmpeg 从 YouTube HLS 拉流并以 MPEG-TS 格式输出到 stdout。"""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", stream_url,
        "-c", "copy",
        "-f", "mpegts",
        "pipe:1",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        while True:
            chunk = await proc.stdout.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()


async def _resolve_and_stream(source_url: str):
    """实时解析 YouTube URL 获取带当前 IP 签名的流地址，然后通过 ffmpeg 转发。"""
    stream_url = await resolve_stream(
        source_url,
        timeout=settings.resolve_timeout_seconds,
        cookies_path=settings.cookies_path,
    )
    if not stream_url:
        return

    async for chunk in _stream_ffmpeg(stream_url):
        yield chunk


@router.get("/proxy/{channel_id}")
async def proxy_stream(channel_id: int, db: Session = Depends(get_db)):
    """实时解析 + ffmpeg 代理，绕过 YouTube HLS IP 绑定限制。"""
    ch = db.get(Channel, channel_id)
    if not ch or not ch.enabled:
        raise HTTPException(status_code=404, detail="Channel not found")
    if not ch.source_url:
        raise HTTPException(status_code=404, detail="No source URL")

    return StreamingResponse(
        _resolve_and_stream(ch.source_url),
        media_type="video/mp2t",
    )
