"""SQLAlchemy setup. SQLite locally, Postgres via DATABASE_URL in production."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_job_columns():
    """Add columns that newer code expects to an existing jobs table.

    create_all() never alters an existing table, so a database created
    before decision_score/language existed (e.g. the Render Postgres)
    would otherwise miss them. Guarded by an inspector check, so it is
    a no-op on fresh databases and on databases that already have the
    columns. Raises on failure — callers must catch and continue.
    """
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("jobs")}
    statements = []
    if "decision_score" not in cols:
        statements.append("ALTER TABLE jobs ADD COLUMN decision_score FLOAT")
    if "language" not in cols:
        statements.append("ALTER TABLE jobs ADD COLUMN language VARCHAR(10)")
    if not statements:
        return
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

