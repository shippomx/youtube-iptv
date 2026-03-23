import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import channels, m3u, health
from app.core.scheduler import create_scheduler, refresh_all_channels


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()

    # 启动后延迟 10s 执行首次全量刷新
    async def _startup_refresh():
        await asyncio.sleep(10)
        await refresh_all_channels()

    asyncio.create_task(_startup_refresh())

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="IPTV SaaS", lifespan=lifespan)

app.include_router(channels.router)
app.include_router(m3u.router)
app.include_router(health.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
