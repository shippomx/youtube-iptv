from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    stream_url = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    group_name = Column(String, default="default")
    enabled = Column(Boolean, default=True)
    last_check = Column(DateTime, nullable=True)
    status = Column(String, default="unknown")  # ok / dead / pending / unknown
    fail_count = Column(Integer, default=0)
