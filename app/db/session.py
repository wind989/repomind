from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置，请先在 .env 中填写 MySQL 连接地址")

    engine_kwargs: dict = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_recycle"] = 3600

    _engine = create_engine(database_url, **engine_kwargs)
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    try:
        db = get_session_factory()()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库尚未配置，请设置 .env 中的 DATABASE_URL 并执行 Alembic 迁移",
        ) from exc
    try:
        yield db
    finally:
        db.close()
