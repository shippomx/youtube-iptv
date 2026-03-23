from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.db.models import Base
import os


def _make_engine(db_url: str):
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, connect_args=connect_args)

    @event.listens_for(engine, "connect")
    def set_wal_mode(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    return engine


def _ensure_data_dir(db_path: str):
    """data/ 目录不存在时自动创建（容器启动时 volume 挂载后可能为空）"""
    dir_path = os.path.dirname(db_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)


def init_db(db_url: str | None = None) -> sessionmaker:
    if db_url is None:
        _ensure_data_dir(settings.db_path)
        db_url = f"sqlite:///{settings.db_path}"
    engine = _make_engine(db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


# 懒加载：import 时不执行，第一次调用 get_session_local() 时才初始化
# 避免测试环境 import database.py 时在磁盘上创建 data/channels.db
_session_local: sessionmaker | None = None


def get_session_local() -> sessionmaker:
    global _session_local
    if _session_local is None:
        _session_local = init_db()
    return _session_local


# 供 scheduler.py 等非 DI 场景直接使用
def SessionLocal():
    return get_session_local()()


def get_db():
    """FastAPI 依赖注入用"""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
