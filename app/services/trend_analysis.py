"""
Advanced trend analysis service.

Replaces the hardcoded "count > 50" spike detection with proper
time-series techniques:

  - 7-day rolling average of daily negative feedback counts
  - Z-score anomaly detection (threshold configurable, default 2.0)
  - Linear regression slope over last 30 days (positive = improving)
  - Category shift detection: flags categories with >20% relative change
    between the most recent 7 days and the prior 7 days

All functions are synchronous and work on pandas DataFrames built from
the Feedback queryset in the caller.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rolling average
# ---------------------------------------------------------------------------

def compute_rolling_average(df: pd.DataFrame, window: int = 7) -> dict[str, float]:
    """
    Compute the rolling mean of daily negative feedback counts.

    Args:
        df:     DataFrame with columns ['created_at', 'sentiment']
        window: Rolling window in days (default 7)

    Returns:
        Dict mapping date strings (YYYY-MM-DD) → rolling average value.
    """
    if df.empty:
        return {}

    neg = df[df["sentiment"] == "negative"].copy()
    neg["date"] = pd.to_datetime(neg["created_at"], utc=True).dt.date
    daily_neg = neg.groupby("date").size().reset_index(name="count")
    daily_neg = daily_neg.sort_values("date")
    daily_neg["rolling"] = daily_neg["count"].rolling(window=window, min_periods=1).mean()
    return {str(row["date"]): round(row["rolling"], 2) for _, row in daily_neg.iterrows()}


# ---------------------------------------------------------------------------
# Z-score anomaly detection
# ---------------------------------------------------------------------------

def detect_anomalies_zscore(series: pd.Series, threshold: float = 2.0) -> list[str]:
    """
    Mark days whose daily negative count is more than `threshold` standard
    deviations above the mean as anomalies.

    Args:
        series:    Date-indexed pd.Series of daily negative feedback counts
        threshold: Z-score threshold (default 2.0)

    Returns:
        List of date strings (YYYY-MM-DD) that are anomalies.
    """
    if series.empty or series.std() == 0:
        return []

    z_scores = (series - series.mean()) / series.std()
    anomaly_dates = series.index[z_scores > threshold].tolist()
    return [str(d)[:10] for d in anomaly_dates]


# ---------------------------------------------------------------------------
# Sentiment slope (linear regression)
# ---------------------------------------------------------------------------

def compute_sentiment_trend(df: pd.DataFrame, lookback_days: int = 30) -> float | None:
    """
    Fit a linear regression to the daily *negative* feedback count over the
    last `lookback_days` days and return the slope.

    Positive slope  → negative feedback increasing (worsening).
    Negative slope  → negative feedback decreasing (improving).

    Returns None if there is insufficient data (fewer than 3 data points).
    """
    if df.empty:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    recent = df[pd.to_datetime(df["created_at"], utc=True) >= cutoff].copy()
    if recent.empty:
        return None

    neg = recent[recent["sentiment"] == "negative"].copy()
    neg["date"] = pd.to_datetime(neg["created_at"], utc=True).dt.date
    daily_neg = neg.groupby("date").size().sort_index()

    if len(daily_neg) < 3:
        return None

    x = np.arange(len(daily_neg), dtype=float)
    y = daily_neg.values.astype(float)
    coeffs = np.polyfit(x, y, 1)
    return round(float(coeffs[0]), 6)  # slope


# ---------------------------------------------------------------------------
# Category shift detection
# ---------------------------------------------------------------------------

def detect_category_shift(
    df: pd.DataFrame,
    lookback: int = 14,
    change_threshold: float = 0.20,
) -> list[dict[str, Any]]:
    """
    Compare category distribution in the most recent 7 days vs the prior 7 days
    (days 7-14 ago) and flag categories whose relative share changed by more
    than `change_threshold` (default 20%).

    Returns:
        List of dicts: [{category, recent_pct, prior_pct, change_pct, direction}, ...]
    """
    if df.empty:
        return []

    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=7)
    prior_start = now - timedelta(days=lookback)

    df_ts = df.copy()
    df_ts["created_at"] = pd.to_datetime(df_ts["created_at"], utc=True)

    recent = df_ts[df_ts["created_at"] >= recent_start]
    prior = df_ts[(df_ts["created_at"] >= prior_start) & (df_ts["created_at"] < recent_start)]

    if recent.empty or prior.empty:
        return []

    def _pct(sub: pd.DataFrame) -> dict[str, float]:
        counts = sub["category"].value_counts()
        total = len(sub)
        return {cat: round(cnt / total, 4) for cat, cnt in counts.items()}

    recent_pcts = _pct(recent)
    prior_pcts = _pct(prior)
    all_cats = set(recent_pcts) | set(prior_pcts)

    shifts = []
    for cat in all_cats:
        r = recent_pcts.get(cat, 0.0)
        p = prior_pcts.get(cat, 0.0)
        if p == 0:
            continue
        change = (r - p) / p
        if abs(change) >= change_threshold:
            shifts.append({
                "category": cat,
                "recent_pct": round(r * 100, 1),
                "prior_pct": round(p * 100, 1),
                "change_pct": round(change * 100, 1),
                "direction": "increase" if change > 0 else "decrease",
            })

    return sorted(shifts, key=lambda s: -abs(s["change_pct"]))


# ---------------------------------------------------------------------------
# Build daily negative series helper
# ---------------------------------------------------------------------------

def _daily_negative_series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    neg = df[df["sentiment"] == "negative"].copy()
    neg["date"] = pd.to_datetime(neg["created_at"], utc=True).dt.date
    return neg.groupby("date").size().sort_index()


# ---------------------------------------------------------------------------
# Full trend report
# ---------------------------------------------------------------------------

def full_trend_report(df: pd.DataFrame) -> dict[str, Any]:
    """
    Run all analyses and return a single dict suitable for the API response.

    Args:
        df: DataFrame with all feedback in the desired window.

    Returns:
        Dict with keys: rolling_average, anomaly_dates, sentiment_slope,
                        category_shifts, trend_status.
    """
    daily_neg = _daily_negative_series(df)
    rolling = compute_rolling_average(df)
    anomaly_dates = detect_anomalies_zscore(daily_neg)
    slope = compute_sentiment_trend(df)
    cat_shifts = detect_category_shift(df)

    trend_status = "normal"
    if anomaly_dates:
        trend_status = "anomaly_detected"
    elif slope is not None and slope > 0.5:
        trend_status = "worsening"

    return {
        "rolling_average": rolling,
        "anomaly_dates": anomaly_dates,
        "sentiment_slope": slope,
        "category_shifts": cat_shifts,
        "trend_status": trend_status,
    }
