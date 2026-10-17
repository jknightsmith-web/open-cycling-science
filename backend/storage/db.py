"""SQLite connection and migrations (spec 8.1 and 8.4)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def engine_for(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA secure_delete = ON")   # deleted rows do not persist in free pages
        cur.close()

    return engine


def upgrade(db_path: Path, revision: str = "head") -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(cfg, revision)
