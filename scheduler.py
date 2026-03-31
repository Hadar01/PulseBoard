"""APScheduler-based heartbeat scheduler — runs every N minutes.

Bug fixes vs. prototype:
1. asyncio.get_event_loop() is deprecated in Python 3.10+ and raises a
   DeprecationWarning (and in some contexts a RuntimeError) when called outside
   of an async context after a loop has already been closed.
   Fixed: use asyncio.run() which creates a fresh event loop, runs the coroutine,
   and cleanly closes the loop — the idiomatic Python 3.10+ pattern.

2. The scheduler was started before the initial heartbeat ran, meaning the very
   first job would fire only after the full interval.  Fixed: run_heartbeat_cycle
   is executed immediately at startup, then the scheduler takes over.
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from routes.heartbeat import run_heartbeat_cycle

logger = logging.getLogger(__name__)


async def heartbeat_job() -> None:
    """Scheduled job: run the full heartbeat pipeline."""
    try:
        digest = await run_heartbeat_cycle()
        logger.info(
            "Heartbeat complete — %d urgent, %d informational",
            len(digest.urgent),
            len(digest.informational),
        )
    except Exception as exc:
        logger.error("Heartbeat job failed: %s", exc, exc_info=True)


def create_scheduler() -> AsyncIOScheduler:
    """Build and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        heartbeat_job,
        "interval",
        minutes=settings.digest_interval_minutes,
        id="heartbeat",
        name="Heartbeat Digest",
        replace_existing=True,
    )
    return scheduler


async def _main() -> None:
    """Async entrypoint: fire an immediate heartbeat then hand off to scheduler."""
    logger.info(
        "Starting heartbeat scheduler (every %d min)",
        settings.digest_interval_minutes,
    )
    # Run an initial cycle immediately so operators see output right away
    await heartbeat_job()

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started — press Ctrl+C to stop")

    try:
        # Keep the event loop alive
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received")
    finally:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
    )
    # FIX: was asyncio.get_event_loop().run_forever() after a run_until_complete() call,
    # which is deprecated in Python 3.10+.  asyncio.run() is the correct idiom.
    asyncio.run(_main())
