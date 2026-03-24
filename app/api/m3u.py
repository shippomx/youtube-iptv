from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(tags=["m3u"])


@router.get("/m3u", response_class=PlainTextResponse)
def get_m3u(
    request: Request,
    include_dead: bool = Query(False),
    db: Session = Depends(get_db),
):
    query = db.query(Channel).filter(
        Channel.enabled == True,
        Channel.stream_url.isnot(None),
    )
    if not include_dead:
        query = query.filter(Channel.status != "dead")

    channels = query.all()

    base_url = str(request.base_url).rstrip("/")
    lines = ["#EXTM3U"]
    for ch in channels:
        logo = f' tvg-logo="{ch.logo_url}"' if ch.logo_url else ""
        group = ch.group_name or "default"
        lines.append(f'#EXTINF:-1{logo} group-title="{group}",{ch.name}')
        lines.append(f"{base_url}/proxy/{ch.id}")

    return "\n".join(lines) + "\n"
