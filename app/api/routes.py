from fastapi import APIRouter, UploadFile, File
from typing import Optional
from collections import Counter
from datetime import datetime, timedelta
from app.schemas import FeedbackCreate
from app.models import Feedback
from app.services.processing import process_feedback
from app.services.alerts import handle_alert

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
    sentiment, category, priority = process_feedback(data.text)

    feedback = await Feedback.create(
        text=data.text,
        sentiment=sentiment,
        category=category,
        priority=priority,
        source=data.source if data.source else "web",
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
    import pandas as pd
    import io

    # Read CSV content
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    # Validate CSV has required column
    if "text" not in df.columns:
        return {"error": "CSV must have 'text' column", "processed": 0}

    results = []
    errors = []

    for idx, row in df.iterrows():
        try:
            text = str(row["text"]).strip()

            if not text or text == "nan":
                errors.append(f"Row {idx + 1}: Empty text")
                continue

            # Process feedback
            sentiment, category, priority = process_feedback(text)

            # Create feedback entry
            feedback = await Feedback.create(
                text=text,
                sentiment=sentiment,
                category=category,
                priority=priority,
                source="csv",
            )

            # Trigger alerts for high priority
            handle_alert(feedback)

            results.append(feedback)

        except Exception as e:
            errors.append(f"Row {idx + 1}: {str(e)}")

    return {
        "processed": len(results),
        "errors": errors[:10],  # Return first 10 errors only
        "total_errors": len(errors),
    }


@router.get("/trends")
async def get_trends():
    """Get trend analysis for the last 7 days with spike detection"""
    # Get feedback from last 7 days
    last_7_days = datetime.utcnow() - timedelta(days=7)
    recent_feedbacks = await Feedback.filter(created_at__gte=last_7_days)

    # Calculate distributions
    sentiments = [f.sentiment for f in recent_feedbacks]
    categories = [f.category for f in recent_feedbacks]
    priorities = [f.priority for f in recent_feedbacks]
    sources = [f.source for f in recent_feedbacks]

    sent_dist = Counter(sentiments)
    cat_dist = Counter(categories)
    prior_dist = Counter(priorities)
    source_dist = Counter(sources)

    # Spike detection
    negative_count = sent_dist.get("negative", 0)
    high_priority_count = prior_dist.get("high", 0)

    alerts = []

    # Detect negative sentiment spike
    if negative_count > 50:
        alerts.append(
            {
                "type": "negative_spike",
                "message": f"High volume of negative feedback detected: {negative_count} in last 7 days",
                "severity": "high",
            }
        )
    elif negative_count > 30:
        alerts.append(
            {
                "type": "negative_warning",
                "message": f"Elevated negative feedback: {negative_count} in last 7 days",
                "severity": "moderate",
            }
        )

    # Detect high priority spike
    if high_priority_count > 20:
        alerts.append(
            {
                "type": "priority_spike",
                "message": f"Spike in high-priority issues: {high_priority_count} in last 7 days",
                "severity": "high",
            }
        )

    return {
        "period": "last_7_days",
        "total_feedback": len(recent_feedbacks),
        "sentiment_distribution": dict(sent_dist),
        "category_distribution": dict(cat_dist),
        "priority_distribution": dict(prior_dist),
        "source_distribution": dict(source_dist),
        "alerts": alerts,
        "trend_status": "spike_detected" if alerts else "normal",
    }
