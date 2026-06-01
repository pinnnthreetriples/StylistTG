from collections.abc import Iterator
from typing import Any

from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.observability.safety_metrics import safety_metrics

_POOL_STAT_ERRORS = (AttributeError, TypeError, ValueError)


class Base(DeclarativeBase):
    pass


def engine_kwargs(database_url: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "future": True,
        "pool_pre_ping": settings.db_pool_pre_ping,
    }
    url = make_url(database_url)
    if url.get_backend_name() == "postgresql":
        connect_args: dict[str, Any] = {
            "connect_timeout": settings.db_connect_timeout_seconds,
        }
        if not _is_neon_pooler_url(url):
            connect_args["options"] = f"-c statement_timeout={settings.db_query_timeout_ms}"
        kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_recycle": settings.db_pool_recycle_seconds,
                "connect_args": connect_args,
            }
        )
    return kwargs


def _is_neon_pooler_url(url: Any) -> bool:
    return url.host is not None and "-pooler." in url.host.lower()


def _record_db_pool_saturation(db_engine: Engine) -> None:
    pool = db_engine.pool
    try:
        size = int(pool.size())  # type: ignore[attr-defined]
        checked_out = int(pool.checkedout())  # type: ignore[attr-defined]
    except _POOL_STAT_ERRORS:
        return
    if size <= 0:
        return
    safety_metrics.db_pool_saturation(pool="default", value=checked_out / size)


engine = create_engine(
    settings.runtime_database_url, **engine_kwargs(settings.runtime_database_url)
)
event.listen(engine, "checkout", lambda *_args: _record_db_pool_saturation(engine))
event.listen(engine, "checkin", lambda *_args: _record_db_pool_saturation(engine))
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
