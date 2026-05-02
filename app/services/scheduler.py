"""
Scheduler Service
Uses APScheduler to run incremental stock updates every 5 minutes
during NSE/BSE market hours (Mon–Fri, 09:15–15:35 IST).
"""
import logging
import os
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

_scheduler: BackgroundScheduler | None = None


def _is_market_hours() -> bool:
    """Return True if current IST time is within NSE trading hours."""
    now     = datetime.now(IST)
    weekday = now.weekday()                   # 0=Mon … 6=Sun
    if weekday >= 5:                          # Saturday / Sunday
        return False
    t = now.time()
    from datetime import time
    return time(9, 15) <= t <= time(15, 35)


def _run_incremental_update():
    """Scheduler job — skips outside market hours to save API calls."""
    if not _is_market_hours():
        logger.debug("Outside market hours — skipping incremental update.")
        return
    logger.info("⏰ Scheduled incremental update triggered.")
    try:
        from app.services.data_ingestion import incremental_update
        incremental_update()
    except Exception as exc:
        logger.error("Scheduled update failed: %s", exc)


def init_scheduler(app):
    """Attach and start the background scheduler to the Flask app."""
    global _scheduler

    # Avoid double-start in Flask's reloader (werkzeug spawns a child process)
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or \
       os.environ.get('FLASK_ENV') == 'production':

        interval = int(os.getenv('UPDATE_INTERVAL_MINUTES', 5))

        _scheduler = BackgroundScheduler(timezone=IST)
        _scheduler.add_job(
            func=_run_incremental_update,
            trigger=IntervalTrigger(minutes=interval, timezone=IST),
            id='incremental_update',
            name='NSE Incremental Data Update',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        _scheduler.start()
        logger.info("Scheduler started — update every %d min during market hours.", interval)

        import atexit
        atexit.register(lambda: _scheduler.shutdown(wait=False))
