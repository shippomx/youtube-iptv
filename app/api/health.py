from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    channels = db.query(Channel).all()
    return {
        "status": "ok",
        "total_channels": len(channels),
        "ok_count": sum(1 for c in channels if c.status == "ok"),
        "dead_count": sum(1 for c in channels if c.status == "dead"),
        "pending_count": sum(1 for c in channels if c.status in ("unknown", "pending")),
        "channels": [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "last_check": c.last_check.isoformat() if c.last_check else None,
            }
            for c in channels
        ],
    }
