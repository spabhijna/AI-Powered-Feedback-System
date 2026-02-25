import asyncio
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from collections import Counter
from datetime import datetime, timedelta, timezone
from app.schemas import FeedbackCreate
from app.models import Feedback
from app.services.processing import process_feedback
from app.services.alerts import handle_alert
from app.services.ingestion import process_csv_data

router = APIRouter()


def generate_insight(cat_dist: dict, sent_dist: dict) -> str:
    """Generate simple insight based on distributions"""
    if cat_dist.get("technical", 0) > 10:
        return "High number of technical issues reported"

    if sent_dist.get("negative", 0) > sent_dist.get("positive", 0):
        return "Customer sentiment is mostly negative"

    return "Overall feedback looks stable"


@router.post("/feedback")
async def create_feedback(data: FeedbackCreate):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, process_feedback, data.text)
    sentiment, category, priority, summary = result

    feedback = await Feedback.create(
        text=data.text,
        sentiment=sentiment,
        category=category,
        priority=priority,
        source=data.source,
        summary=summary,
    )

    # Centralized alert handling
    handle_alert(feedback)

    return feedback


@router.get("/feedback")
async def get_feedback(
    category: Optional[str] = None,
    sentiment: Optional[str] = None,
    priority: Optional[str] = None,
    source: Optional[str] = None,
):
    """Get feedback with optional filtering"""
    query = Feedback.all()

    if category:
        query = query.filter(category=category)

    if sentiment:
        query = query.filter(sentiment=sentiment)

    if priority:
        query = query.filter(priority=priority)

    if source:
        query = query.filter(source=source)

    return await query


@router.get("/analytics")
async def get_analytics():
    """Get aggregated analytics and insights"""
    feedbacks = await Feedback.all()

    sentiments = [f.sentiment for f in feedbacks]
    categories = [f.category for f in feedbacks]
    priorities = [f.priority for f in feedbacks]

    sent_dist = Counter(sentiments)
    cat_dist = Counter(categories)
    prior_dist = Counter(priorities)

    insight = generate_insight(cat_dist, sent_dist)

    return {
        "total_feedback": len(feedbacks),
        "sentiment_distribution": dict(sent_dist),
        "category_distribution": dict(cat_dist),
        "priority_distribution": dict(prior_dist),
        "insight": insight,
    }


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload and process CSV file with bulk feedback"""
    content = await file.read()
    result = await process_csv_data(content)
    return result


@router.get("/trends")
async def get_trends():
    """Get advanced trend analysis for the last 30 days."""
    import pandas as pd
    from app.services.trend_analysis import full_trend_report
    from app.services.alerts import fire_trend_alerts

    # Pull 30 days for regression; 7-day window for spike/distribution summary
    last_30_days = datetime.now(timezone.utc) - timedelta(days=30)
    last_7_days = datetime.now(timezone.utc) - timedelta(days=7)

    all_feedbacks = await Feedback.filter(created_at__gte=last_30_days)
    recent_feedbacks = [f for f in all_feedbacks if f.created_at >= last_7_days]

    # Build DataFrame for trend analysis
    df = pd.DataFrame([
        {
            "created_at": f.created_at,
            "sentiment": f.sentiment,
            "category": f.category,
            "priority": f.priority,
            "source": f.source,
        }
        for f in all_feedbacks
    ])

    trend_data = full_trend_report(df)

    # Build 7-day distributions
    sentiments = [f.sentiment for f in recent_feedbacks]
    categories = [f.category for f in recent_feedbacks]
    priorities = [f.priority for f in recent_feedbacks]
    sources = [f.source for f in recent_feedbacks]

    sent_dist = dict(Counter(sentiments))
    cat_dist = dict(Counter(categories))
    prior_dist = dict(Counter(priorities))
    source_dist = dict(Counter(sources))

    # Build daily counts for the 7-day window
    daily_counts: dict = {}
    for fb in recent_feedbacks:
        day = fb.created_at.strftime("%Y-%m-%d")
        daily_counts.setdefault(day, {"positive": 0, "negative": 0, "neutral": 0})
        daily_counts[day][fb.sentiment] = daily_counts[day].get(fb.sentiment, 0) + 1

    # Persist Z-score alerts
    alerts = await fire_trend_alerts(trend_data)

    return {
        "period": "last_7_days",
        "total_feedback": len(recent_feedbacks),
        "sentiment_distribution": sent_dist,
        "category_distribution": cat_dist,
        "priority_distribution": prior_dist,
        "source_distribution": source_dist,
        "daily_counts": daily_counts,
        "rolling_average": trend_data["rolling_average"],
        "anomaly_dates": trend_data["anomaly_dates"],
        "sentiment_slope": trend_data["sentiment_slope"],
        "category_shifts": trend_data["category_shifts"],
        "alerts": alerts,
        "trend_status": trend_data["trend_status"],
    }


# ---------------------------------------------------------------------------
# Scraper routes (Phase 3)
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    source_type: str           # "google_play" | "app_store" | "web"
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    country: Optional[str] = "us"
    count: int = 50
    url: Optional[str] = None
    css_selector: Optional[str] = "p"
    fetch_all: bool = False    # When True, paginate through all available reviews


@router.post("/sources/scrape")
async def trigger_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    """Manually trigger a scrape for a given source."""
    from app.services.ingestion import ingest_scraped_items

    async def _run():
        if req.source_type == "google_play":
            if not req.app_id:
                return
            from app.services.scrapers.play_store import scrape_reviews
            items = scrape_reviews(
                app_id=req.app_id,
                count=req.count,
                country=req.country or "us",
                fetch_all=req.fetch_all,
            )
            await ingest_scraped_items(items)

        elif req.source_type == "app_store":
            if not req.app_id or not req.app_name:
                return
            from app.services.scrapers.app_store_scraper import scrape_reviews
            items = scrape_reviews(
                app_name=req.app_name,
                app_id=req.app_id,
                country=req.country or "us",
                count=req.count,
            )
            await ingest_scraped_items(items)

        elif req.source_type == "web":
            if not req.url:
                return
            from app.services.scrapers.web_scraper import scrape_url
            items = scrape_url(url=req.url, css_selector=req.css_selector or "p")
            await ingest_scraped_items(items)

    background_tasks.add_task(_run)
    return {"status": "scrape_queued", "source_type": req.source_type}


@router.get("/sources/status")
async def get_sources_status():
    """Return configured scraper jobs and their last-run status."""
    from app.services.scheduler import get_status
    return get_status()


@router.get("/sources/scheduler-health")
async def get_scheduler_health():
    """Return detailed scheduler health information including DB configs."""
    from app.services.scheduler import get_status
    from app.models import ScraperConfig
    
    # Get basic scheduler status
    scheduler_status = get_status()
    
    # Get database configs with their status
    configs = await ScraperConfig.all().order_by("id")
    db_configs = []
    
    for c in configs:
        db_configs.append({
            "id": c.id,
            "source_type": c.source_type,
            "label": c.label or c.app_id or c.app_name or f"Config {c.id}",
            "enabled": c.enabled,
            "last_status": c.last_status,
            "last_run_at": str(c.last_run_at) if c.last_run_at else None,
            "last_run_count": c.last_run_count,
            "last_error": c.last_error,
            "retry_count": c.retry_count,
            "interval_hours": c.interval_hours,
        })
    
    return {
        "scheduler_enabled": scheduler_status.get("enabled", False),
        "total_jobs": len(scheduler_status.get("jobs", {})),
        "jobs": scheduler_status.get("jobs", {}),
        "database_configs": db_configs,
        "database_configs_count": len(db_configs),
        "enabled_configs_count": sum(1 for c in configs if c.enabled),
    }


# ---------------------------------------------------------------------------
# Scraper config CRUD
# ---------------------------------------------------------------------------

class ScraperConfigCreate(BaseModel):
    source_type: str
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    country: str = "us"
    count: int = 50
    interval_hours: int = 6
    enabled: bool = True
    label: Optional[str] = None


@router.get("/sources/configs")
async def list_scraper_configs():
    from app.models import ScraperConfig
    configs = await ScraperConfig.all().order_by("id")
    return [
        {
            "id": c.id,
            "source_type": c.source_type,
            "app_id": c.app_id,
            "app_name": c.app_name,
            "country": c.country,
            "count": c.count,
            "interval_hours": c.interval_hours,
            "enabled": c.enabled,
            "label": c.label or c.app_id or c.app_name or "",
            "last_run_at": str(c.last_run_at) if c.last_run_at else None,
            "last_run_count": c.last_run_count,
            "last_status": c.last_status,
            "last_error": c.last_error,
            "retry_count": c.retry_count,
        }
        for c in configs
    ]


@router.post("/sources/configs")
async def create_scraper_config(req: ScraperConfigCreate):
    from app.models import ScraperConfig
    from app.services.scheduler import reload_db_jobs
    c = await ScraperConfig.create(**req.model_dump())
    await reload_db_jobs()
    return {"id": c.id, "status": "created"}


@router.delete("/sources/configs/{config_id}")
async def delete_scraper_config(config_id: int):
    from app.models import ScraperConfig
    from app.services.scheduler import reload_db_jobs
    deleted = await ScraperConfig.filter(id=config_id).delete()
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Config not found")
    await reload_db_jobs()
    return {"status": "deleted"}


@router.patch("/sources/configs/{config_id}/toggle")
async def toggle_scraper_config(config_id: int):
    from app.models import ScraperConfig
    from app.services.scheduler import reload_db_jobs
    c = await ScraperConfig.get_or_none(id=config_id)
    if not c:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Config not found")
    c.enabled = not c.enabled
    await c.save()
    await reload_db_jobs()
    return {"id": c.id, "enabled": c.enabled}


# ---------------------------------------------------------------------------
# Report routes (Phase 5)
# ---------------------------------------------------------------------------

@router.get("/reports/generate")
async def generate_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Generate and stream a PDF analytics report."""
    from app.services.report_generator import generate_report as _gen

    from datetime import date

    start = (
        datetime.strptime(start_date, "%Y-%m-%d")
        if start_date
        else datetime.now(timezone.utc) - timedelta(days=30)
    )
    end = (
        datetime.strptime(end_date, "%Y-%m-%d")
        if end_date
        else datetime.now(timezone.utc)
    )

    loop = asyncio.get_event_loop()
    pdf_bytes = await loop.run_in_executor(None, _gen, start, end)

    filename = f"feedback_report_{start.date()}_{end.date()}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Alerts history
# ---------------------------------------------------------------------------

@router.get("/alerts")
async def get_alerts(limit: int = 50):
    """Return the most recent persisted trend alerts."""
    from app.models import Alert
    alerts = await Alert.all().order_by("-triggered_at").limit(limit)
    return [
        {
            "id": a.id,
            "type": a.type,
            "severity": a.severity,
            "message": a.message,
            "triggered_at": str(a.triggered_at),
        }
        for a in alerts
    ]
