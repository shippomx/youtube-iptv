import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(tags=["proxy"])


@router.get("/proxy/{channel_id}")
async def proxy_stream(channel_id: int, request: Request, db: Session = Depends(get_db)):
    """代理 YouTube HLS manifest，解决 IP 绑定问题。"""
    ch = db.get(Channel, channel_id)
    if not ch or not ch.stream_url or ch.status == "dead":
        raise HTTPException(status_code=404, detail="Stream not available")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        try:
            r = await client.get(ch.stream_url)
            r.raise_for_status()
        except Exception:
            raise HTTPException(status_code=502, detail="Failed to fetch stream from upstream")

    return Response(content=r.content, media_type="application/x-mpegurl")
