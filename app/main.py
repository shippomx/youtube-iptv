from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import channels, m3u, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="IPTV SaaS", lifespan=lifespan)

app.include_router(channels.router)
app.include_router(m3u.router)
app.include_router(health.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
