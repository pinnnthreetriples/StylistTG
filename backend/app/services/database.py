from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


_sqlite_test_engines: set[Engine] = set()


def create_sqlite_test_session_factory() -> tuple[sessionmaker[Session], Engine]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    _sqlite_test_engines.add(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True), engine


def dispose_sqlite_test_engines() -> None:
    for engine in tuple(_sqlite_test_engines):
        engine.dispose()
        _sqlite_test_engines.discard(engine)
