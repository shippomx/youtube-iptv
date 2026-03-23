from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(tags=["m3u"])


@router.get("/m3u", response_class=PlainTextResponse)
def get_m3u(
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

    lines = ["#EXTM3U"]
    for ch in channels:
        logo = f' tvg-logo="{ch.logo_url}"' if ch.logo_url else ""
        group = ch.group_name or "default"
        lines.append(f'#EXTINF:-1{logo} group-title="{group}",{ch.name}')
        lines.append(ch.stream_url)

    return "\n".join(lines) + "\n"
