"""Database engine + session helpers."""
from pathlib import Path
from contextlib import contextmanager

from sqlmodel import SQLModel, create_engine, Session

from .config import settings

Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

_engine = create_engine(
    f"sqlite:///{settings.data_dir}/pocketscribe.db",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    # import models so metadata is populated before create_all
    from . import models  # noqa: F401
    SQLModel.metadata.create_all(_engine)


def get_engine():
    return _engine


@contextmanager
def session_scope() -> Session:
    s = Session(_engine)
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
