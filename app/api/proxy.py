import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(tags=["proxy"])

# ffmpeg 参数：从 YouTube HLS 拉流，以 MPEG-TS 格式输出（兼容 IINA/VLC）
_FFMPEG_CMD = [
    "ffmpeg", "-hide_banner", "-loglevel", "error",
    "-re",
    "-i", "{stream_url}",
    "-c", "copy",
    "-f", "mpegts",
    "pipe:1",
]


async def _stream_ffmpeg(stream_url: str):
    cmd = [c.replace("{stream_url}", stream_url) for c in _FFMPEG_CMD]
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
    """通过 ffmpeg 在服务器端拉取 YouTube HLS 并转发，解决 IP 绑定问题。"""
    ch = db.get(Channel, channel_id)
    if not ch or not ch.stream_url or ch.status == "dead":
        raise HTTPException(status_code=404, detail="Stream not available")

    return StreamingResponse(
        _stream_ffmpeg(ch.stream_url),
        media_type="video/mp2t",
    )
