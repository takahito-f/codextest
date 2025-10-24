"""Database setup and session management."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine = None
_SessionFactory = None


def init_engine(db_url: str) -> None:
    global _engine, _SessionFactory
    if _engine is None:
        kwargs = {"future": True}
        if db_url.startswith("sqlite"):
            kwargs.update({"connect_args": {"check_same_thread": False}})
            if db_url.endswith(":memory:"):
                kwargs["poolclass"] = StaticPool
        else:
            kwargs["pool_pre_ping"] = True
        _engine = create_engine(db_url, **kwargs)
        _SessionFactory = scoped_session(sessionmaker(bind=_engine, autoflush=False, autocommit=False))
        logger.info("Database engine initialised")


def get_engine():
    if _engine is None:
        raise RuntimeError("Database engine not initialised")
    return _engine


def get_session() -> Session:
    if _SessionFactory is None:
        raise RuntimeError("Session factory not initialised")
    return _SessionFactory()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
