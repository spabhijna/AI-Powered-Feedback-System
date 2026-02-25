"""
APScheduler background scheduler for automated data ingestion.

Jobs come from two sources (merged at startup and on demand):
  1. Environment variables  – legacy / quick-start
  2. ScraperConfig DB rows  – managed via the dashboard UI

Environment variables (all optional):
    SCHEDULER_ENABLED          – "true" to activate (default "false")
    EMAIL_POLL_MINUTES         – email inbox poll interval (default 30)
    PLAY_STORE_APP_ID          – enable Play Store scraping if set
    PLAY_STORE_SCRAPE_HOURS    – scrape interval in hours (default 6)
    PLAY_STORE_COUNT           – reviews per run (default 50)
    APP_STORE_APP_NAME         – enable App Store scraping if set
    APP_STORE_APP_ID           – numeric App Store ID
    APP_STORE_COUNTRY          – country code (default "us")
    APP_STORE_SCRAPE_HOURS     – scrape interval in hours (default 6)
"""

import asyncio
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED  # type: ignore

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

# Track last-run metadata per job
_job_status: dict = {}


def _run_async(coro):
    """Run a coroutine in the current or a new event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)


# ---------------------------------------------------------------------------
# Generic job runner (used for DB-driven configs)
# ---------------------------------------------------------------------------

def _run_scraper_config(config_id: int):
    """Execute a scrape for a ScraperConfig row identified by *config_id*.

    APScheduler calls this from its own background thread.  We create a fresh
    event loop for each run so we never touch the FastAPI event loop.
    """
    async def _inner():
        from app.models import ScraperConfig
        from app.services.ingestion import ingest_scraped_items
        from datetime import datetime, timezone
        import traceback

        c = await ScraperConfig.get_or_none(id=config_id)
        if c is None:
            logger.warning("ScraperConfig %d not found, removing job", config_id)
            return
        
        if not c.enabled:
            logger.debug("ScraperConfig %d is disabled, skipping", config_id)
            return

        # Update status to running
        c.last_status = "running"
        await c.save()
        
        label = c.label or c.app_id or c.app_name or str(c.id)
        logger.info("Starting %s scrape for: %s (config_id=%d)", c.source_type, label, config_id)

        items = []
        error_msg = None
        
        try:
            if c.source_type == "google_play":
                from app.services.scrapers.play_store import scrape_reviews
                items = scrape_reviews(
                    app_id=c.app_id or "",
                    count=c.count,
                    country=c.country,
                )
            elif c.source_type == "app_store":
                from app.services.scrapers.app_store_scraper import scrape_reviews
                items = scrape_reviews(
                    app_name=c.app_name or "",
                    app_id=c.app_id or "",
                    country=c.country,
                    count=c.count,
                )
            else:
                error_msg = f"Unknown source_type: {c.source_type}"
                raise ValueError(error_msg)

            # Ingest scraped items
            if items:
                result = await ingest_scraped_items(items)
                logger.info(
                    "Scraper %d ingested: %d processed, %d skipped, %d errors",
                    config_id, result.get("processed", 0), 
                    result.get("skipped", 0), result.get("total_errors", 0)
                )
            else:
                logger.warning("Scraper %d returned 0 items", config_id)

            # Success - update status
            c.last_run_at = datetime.now(timezone.utc)
            c.last_run_count = len(items)
            c.last_status = "success"
            c.last_error = None
            c.retry_count = 0  # Reset retry count on success
            await c.save()

            job_key = f"db_{config_id}"
            _job_status[job_key] = {
                "status": "success",
                "last_count": len(items),
                "last_run": str(c.last_run_at),
            }
            logger.info("Scraper %d completed successfully: %d items", config_id, len(items))

        except Exception as exc:
            # Error - update status with details
            error_msg = str(exc)
            stack_trace = traceback.format_exc()
            
            c.last_run_at = datetime.now(timezone.utc)
            c.last_status = "error"
            c.last_error = f"{error_msg}\\n\\nStack trace:\\n{stack_trace}"
            c.retry_count += 1
            await c.save()

            job_key = f"db_{config_id}"
            _job_status[job_key] = {
                "status": "error",
                "error": error_msg,
                "last_run": str(c.last_run_at),
                "retry_count": c.retry_count,
            }
            
            logger.error(
                "Scraper %d (%s) failed (retry %d): %s",
                config_id, label, c.retry_count, error_msg
            )
            logger.debug("Full stack trace for scraper %d:\\n%s", config_id, stack_trace)

    # Always spin up a dedicated loop — APScheduler threads must not touch the
    # FastAPI/uvicorn event loop.
    try:
        asyncio.run(_inner())
    except Exception as exc:
        logger.error("Fatal error in scraper job %d: %s", config_id, exc)


# ---------------------------------------------------------------------------
# Legacy env-var job handlers
# ---------------------------------------------------------------------------

def _job_email_poll():
    from app.services.ingestion import process_emails_from_inbox
    import traceback
    
    _job_status["email"] = {"status": "running"}
    
    try:
        asyncio.run(process_emails_from_inbox())
        _job_status["email"] = {"status": "idle"}
        logger.info("Email polling completed successfully")
    except Exception as exc:
        error_msg = str(exc)
        _job_status["email"] = {"status": "error", "error": error_msg}
        logger.error("Email polling failed: %s", error_msg)
        logger.debug("Email polling stack trace:\\n%s", traceback.format_exc())


def _job_play_store():
    from app.services.scrapers.play_store import scrape_reviews
    from app.services.ingestion import ingest_scraped_items
    import traceback

    app_id = os.getenv("PLAY_STORE_APP_ID", "")
    count = int(os.getenv("PLAY_STORE_COUNT", "50"))

    _job_status["play_store"] = {"status": "running", "app_id": app_id}
    
    try:
        logger.info("Starting Play Store scrape for: %s", app_id)
        items = scrape_reviews(app_id=app_id, count=count)
        result = asyncio.run(ingest_scraped_items(items))
        
        _job_status["play_store"] = {
            "status": "idle",
            "last_count": len(items),
            "app_id": app_id,
            "processed": result.get("processed", 0),
            "skipped": result.get("skipped", 0),
        }
        logger.info(
            "Play Store job completed: %d items (%d processed, %d skipped)",
            len(items), result.get("processed", 0), result.get("skipped", 0)
        )
    except Exception as exc:
        error_msg = str(exc)
        _job_status["play_store"] = {
            "status": "error",
            "error": error_msg,
            "app_id": app_id
        }
        logger.error("Play Store scraping failed for %s: %s", app_id, error_msg)
        logger.debug("Play Store stack trace:\\n%s", traceback.format_exc())


def _job_app_store():
    from app.services.scrapers.app_store_scraper import scrape_reviews
    from app.services.ingestion import ingest_scraped_items
    import traceback

    app_name = os.getenv("APP_STORE_APP_NAME", "")
    app_id = os.getenv("APP_STORE_APP_ID", "")
    country = os.getenv("APP_STORE_COUNTRY", "us")
    count = int(os.getenv("APP_STORE_COUNT", "50"))

    _job_status["app_store"] = {"status": "running", "app_id": app_id}
    
    try:
        logger.info("Starting App Store scrape for: %s", app_name)
        items = scrape_reviews(app_name=app_name, app_id=app_id, country=country, count=count)
        result = asyncio.run(ingest_scraped_items(items))
        
        _job_status["app_store"] = {
            "status": "idle",
            "last_count": len(items),
            "app_id": app_id,
            "processed": result.get("processed", 0),
            "skipped": result.get("skipped", 0),
        }
        logger.info(
            "App Store job completed: %d items (%d processed, %d skipped)",
            len(items), result.get("processed", 0), result.get("skipped", 0)
        )
    except Exception as exc:
        error_msg = str(exc)
        _job_status["app_store"] = {
            "status": "error",
            "error": error_msg,
            "app_id": app_id
        }
        logger.error("App Store scraping failed for %s: %s", app_name, error_msg)
        logger.debug("App Store stack trace:\\n%s", traceback.format_exc())


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

def _on_job_event(event):
    if event.exception:
        logger.error("Scheduler job %s failed: %s", event.job_id, event.exception)


def _add_env_jobs():
    """Register jobs sourced from environment variables."""
    if not _scheduler:
        return

    env_jobs_added = []
    
    email_interval = int(os.getenv("EMAIL_POLL_MINUTES", "30"))
    if os.getenv("EMAIL_HOST"):
        _scheduler.add_job(_job_email_poll, "interval", minutes=email_interval, id="email", replace_existing=True)
        env_jobs_added.append(f"Email polling every {email_interval} minutes")

    play_hours = int(os.getenv("PLAY_STORE_SCRAPE_HOURS", "6"))
    if os.getenv("PLAY_STORE_APP_ID"):
        app_id = os.getenv("PLAY_STORE_APP_ID")
        _scheduler.add_job(_job_play_store, "interval", hours=play_hours, id="play_store", replace_existing=True)
        env_jobs_added.append(f"Play Store ({app_id}) every {play_hours}h")

    app_hours = int(os.getenv("APP_STORE_SCRAPE_HOURS", "6"))
    if os.getenv("APP_STORE_APP_NAME"):
        app_name = os.getenv("APP_STORE_APP_NAME")
        _scheduler.add_job(_job_app_store, "interval", hours=app_hours, id="app_store", replace_existing=True)
        env_jobs_added.append(f"App Store ({app_name}) every {app_hours}h")
    
    if env_jobs_added:
        logger.info("Environment-based jobs configured:")
        for job_desc in env_jobs_added:
            logger.info("  • %s", job_desc)
    else:
        logger.debug("No environment-based scraper jobs configured")


async def _sync_db_jobs():
    """(Re-)register APScheduler jobs for every enabled ScraperConfig row."""
    if not _scheduler:
        logger.warning("Scheduler not initialized, cannot sync DB jobs")
        return
    
    logger.debug("Starting DB job synchronization...")
    
    try:
        from app.models import ScraperConfig

        # Remove stale DB jobs first
        removed_count = 0
        for job in list(_scheduler.get_jobs()):
            if job.id.startswith("db_"):
                job.remove()
                removed_count += 1
        
        if removed_count > 0:
            logger.debug("Removed %d existing DB jobs", removed_count)

        configs = await ScraperConfig.filter(enabled=True)
        
        if not configs:
            logger.info("No enabled ScraperConfig records found in database")
            return
        
        registered_count = 0
        for c in configs:
            job_id = f"db_{c.id}"
            _scheduler.add_job(
                _run_scraper_config,
                "interval",
                hours=c.interval_hours,
                id=job_id,
                args=[c.id],
                replace_existing=True,
            )
            label = c.label or c.app_id or c.app_name or str(c.id)
            logger.info(
                "✓ Registered DB scraper: %s [%s / %s] every %dh (job_id=%s)",
                label, c.source_type, c.country, c.interval_hours, job_id
            )
            registered_count += 1
        
        logger.info("Successfully registered %d database-configured scraper job(s)", registered_count)
        
    except ImportError as exc:
        logger.error("Failed to import ScraperConfig model: %s", exc)
        logger.error("Database may not be initialized yet")
    except Exception as exc:
        logger.error("Failed to sync DB scraper jobs: %s", exc, exc_info=True)
        logger.error("Dashboard-configured scrapers will not run until this is resolved")


async def reload_db_jobs():
    """Called by API routes when a ScraperConfig is created / deleted / toggled."""
    await _sync_db_jobs()


async def load_db_jobs_on_startup():
    """Called after Tortoise ORM is ready so DB-sourced jobs can be scheduled."""
    logger.info("Loading database-configured scraper jobs...")
    await _sync_db_jobs()
    if _scheduler:
        jobs = _scheduler.get_jobs()
        logger.info("=" * 60)
        logger.info("Scheduler Status:")
        logger.info("  Total jobs: %d", len(jobs))
        for job in jobs:
            logger.info("    - %s: next run at %s", job.id, job.next_run_time)
        logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Public start / stop
# ---------------------------------------------------------------------------

def start_scheduler():
    """Create and start the background scheduler (env jobs only at this point)."""
    global _scheduler

    if os.getenv("SCHEDULER_ENABLED", "false").lower() != "true":
        logger.info("⏸️  Scheduler disabled (set SCHEDULER_ENABLED=true to enable)")
        return

    logger.info("Starting APScheduler...")
    _scheduler = BackgroundScheduler()
    _scheduler.add_listener(_on_job_event, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    _add_env_jobs()
    _scheduler.start()
    
    env_jobs = len(_scheduler.get_jobs())
    if env_jobs > 0:
        logger.info("✅ Scheduler started with %d environment-based job(s)", env_jobs)
    else:
        logger.info("✅ Scheduler started (no environment-based jobs configured)")
        logger.info("   Waiting for database-configured jobs...")


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_status() -> dict:
    """Return current status of all configured scraper jobs."""
    configured = {}
    if _scheduler:
        for job in _scheduler.get_jobs():
            configured[job.id] = {
                "next_run": str(job.next_run_time),
                **_job_status.get(job.id, {"status": "idle"}),
            }
    return {
        "enabled": _scheduler is not None and _scheduler.running,
        "jobs": configured,
    }


