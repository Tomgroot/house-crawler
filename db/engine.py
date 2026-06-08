import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()


class Base(DeclarativeBase):
    pass


_database_url = os.getenv("DATABASE_URL", "sqlite:///./house_crawler.db")
_engine = create_engine(_database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_engine():
    return _engine


def get_session() -> Session:
    return SessionLocal()


def init_db() -> None:
    from db import models  # noqa: F401 — ensures models are registered before create_all

    Base.metadata.create_all(bind=_engine)
