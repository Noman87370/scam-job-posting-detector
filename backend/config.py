"""Configuration — everything comes from environment variables.

Local defaults use SQLite; production sets DATABASE_URL (Postgres).
No secrets are ever committed; see .env.example.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(BASE_DIR, "jobs.db"),
)
# Render/Heroku style Postgres URLs use postgres:// — SQLAlchemy wants postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "")
MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(ROOT_DIR, "model"))
FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR", os.path.join(BASE_DIR, "static")
)
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
ARBEITNOW_MAX_PAGES = int(os.environ.get("ARBEITNOW_MAX_PAGES", "10"))
INGEST_INTERVAL_MINUTES = int(os.environ.get("INGEST_INTERVAL_MINUTES", "30"))
RUN_SCHEDULER = os.environ.get("RUN_SCHEDULER", "true").lower() in ("1", "true", "yes")
