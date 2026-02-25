"""
Centralised alert handling.

handle_alert()    – fires on every new feedback item (high priority)
fire_trend_alerts() – fires from /trends endpoint based on Z-score anomalies
                    and sentiment slope; persists to the Alert DB table.
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def handle_alert(feedback) -> None:
    """
    Inspect a newly created Feedback record and log/persist a high-priority alert.
    """
    if feedback.priority == "high":
        logger.warning(
            "HIGH PRIORITY ALERT | id=%s | category=%s | sentiment=%s | source=%s | text=%.100s",
            feedback.id,
            feedback.category,
            feedback.sentiment,
            feedback.source,
            feedback.text,
        )


async def fire_trend_alerts(trend_data: dict[str, Any]) -> list[dict]:
    """
    Evaluate trend analysis results and persist actionable alerts to the DB.

    Triggers:
    - Z-score anomaly on any date in the last 7 days → high severity
    - Worsening sentiment slope (> 0.5 per day) → moderate severity
    - Large category shift (>= 40% relative change) → moderate severity

    Returns:
        List of alert dicts (same format as previous spike detection) for
        inclusion in the API response.
    """
    from app.models import Alert

    alerts = []
    now = datetime.now(timezone.utc)

    anomaly_dates = trend_data.get("anomaly_dates", [])
    if anomaly_dates:
        msg = f"Z-score anomaly detected on: {', '.join(anomaly_dates)}"
        alert = await Alert.create(
            type="zscore_anomaly",
            severity="high",
            message=msg,
        )
        alerts.append({
            "type": alert.type,
            "severity": alert.severity,
            "message": alert.message,
            "triggered_at": str(alert.triggered_at),
        })

    slope = trend_data.get("sentiment_slope")
    if slope is not None and slope > 0.5:
        msg = f"Negative feedback is increasingly trending upward (slope={slope:.4f}/day over 30 days)"
        alert = await Alert.create(
            type="sentiment_worsening",
            severity="moderate",
            message=msg,
        )
        alerts.append({
            "type": alert.type,
            "severity": alert.severity,
            "message": alert.message,
            "triggered_at": str(alert.triggered_at),
        })

    for shift in trend_data.get("category_shifts", []):
        if abs(shift.get("change_pct", 0)) >= 40:
            cat = shift["category"].replace("_", " ").title()
            direction = shift["direction"]
            msg = (
                f"Category '{cat}' has {direction}d by {abs(shift['change_pct'])}% "
                f"versus the prior 7 days"
            )
            alert = await Alert.create(
                type="category_shift",
                severity="moderate",
                message=msg,
            )
            alerts.append({
                "type": alert.type,
                "severity": alert.severity,
                "message": alert.message,
                "triggered_at": str(alert.triggered_at),
            })

    return alerts
