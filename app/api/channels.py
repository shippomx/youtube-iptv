from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelCreate(BaseModel):
    name: str
    source_url: str
    logo_url: Optional[str] = None
    group_name: str = "default"


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    group_name: Optional[str] = None
    enabled: Optional[bool] = None


class ChannelOut(BaseModel):
    id: int
    name: str
    source_url: str
    stream_url: Optional[str]
    logo_url: Optional[str]
    group_name: str
    enabled: bool
    status: str
    last_check: Optional[datetime]
    fail_count: int

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ChannelOut])
def list_channels(db: Session = Depends(get_db)):
    return db.query(Channel).all()


@router.post("", response_model=ChannelOut, status_code=201)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db)):
    existing = db.query(Channel).filter(Channel.source_url == payload.source_url).first()
    if existing:
        raise HTTPException(status_code=409, detail="source_url already exists")
    ch = Channel(**payload.model_dump())
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(channel_id: int, payload: ChannelUpdate, db: Session = Depends(get_db)):
    ch = db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(ch, field, value)
    db.commit()
    db.refresh(ch)
    return ch


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    ch = db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    db.delete(ch)
    db.commit()


@router.post("/refresh-all", status_code=202)
def refresh_all(background_tasks: BackgroundTasks):
    from app.core.scheduler import refresh_all_channels
    background_tasks.add_task(refresh_all_channels)
    return {"message": "full refresh triggered"}


@router.post("/{channel_id}/refresh", status_code=202)
def refresh_channel(channel_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ch = db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    from app.core.scheduler import refresh_single_channel
    background_tasks.add_task(refresh_single_channel, channel_id)
    return {"message": "refresh triggered"}
