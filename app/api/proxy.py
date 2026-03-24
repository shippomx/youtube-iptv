import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(tags=["proxy"])

# yt-dlp 直接下载并输出到 stdout（处理所有 YouTube 认证），ffmpeg 仅做格式转换
_YTDLP_ARGS = [
    "yt-dlp", "--no-update",
    "-f", "b",
    "--extractor-args", "youtube:player_client=android",
    "--downloader", "ffmpeg",
    "--downloader-args", "ffmpeg_i:-re",
    "-o", "-",   # 输出到 stdout
]


async def _stream_channel(source_url: str, cookies_path: str = ""):
    """yt-dlp 下载 YouTube HLS 并输出 MPEG-TS 到 stdout。"""
    import os
    cmd = list(_YTDLP_ARGS)
    if cookies_path and os.path.isfile(cookies_path):
        cmd += ["--cookies", cookies_path]
    cmd.append(source_url)

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


@router.get("/proxy/{channel_id}")
async def proxy_stream(channel_id: int, db: Session = Depends(get_db)):
    """yt-dlp 全程代理 YouTube 直播流（处理认证+段下载），客户端收到 MPEG-TS。"""
    ch = db.get(Channel, channel_id)
    if not ch or not ch.enabled:
        raise HTTPException(status_code=404, detail="Channel not found")
    if not ch.source_url:
        raise HTTPException(status_code=404, detail="No source URL")

    return StreamingResponse(
        _stream_channel(ch.source_url, settings.cookies_path),
        media_type="video/mp2t",
    )
