"""In-process scheduler: re-ingest every INGEST_INTERVAL_MINUTES.

Runs inside the web service (APScheduler). A GitHub Actions workflow
(.github/workflows/ingest.yml) additionally POSTs to /api/jobs/ingest on
the same schedule, so ingestion also happens if the web service sleeps.
Failures are logged and recorded on the IngestRun row; they never crash
the app.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .config import INGEST_INTERVAL_MINUTES
from .ingest import ingest_arbeitnow

logger = logging.getLogger(__name__)


def _run() -> None:
    try:
        result = ingest_arbeitnow()
        logger.info("Scheduled ingest finished: %s", result)
    except Exception:  # noqa: BLE001 — scheduler must never die
        logger.exception("Scheduled ingest failed")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run,
        "interval",
        minutes=INGEST_INTERVAL_MINUTES,
        id="arbeitnow-ingest",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Ingest scheduler started (every %s minutes)", INGEST_INTERVAL_MINUTES
    )
    return scheduler
