"""
Unit tests for trend analysis, scraper modules, and LLM service.
All external calls are mocked.
"""

import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------

from app.services.trend_analysis import (
    compute_rolling_average,
    detect_anomalies_zscore,
    compute_sentiment_trend,
    detect_category_shift,
    full_trend_report,
)


def _make_df(days: int = 30, daily_neg: int = 5, daily_pos: int = 10) -> pd.DataFrame:
    """Build a synthetic feedback DataFrame."""
    now = datetime.utcnow()
    rows = []
    for i in range(days):
        ts = now - timedelta(days=days - i)
        for _ in range(daily_neg):
            rows.append({"created_at": ts, "sentiment": "negative", "category": "technical", "priority": "high", "source": "api"})
        for _ in range(daily_pos):
            rows.append({"created_at": ts, "sentiment": "positive", "category": "general", "priority": "low", "source": "web"})
    return pd.DataFrame(rows)


def test_rolling_average_returns_dict():
    df = _make_df(14)
    result = compute_rolling_average(df, window=7)
    assert isinstance(result, dict)
    assert len(result) > 0


def test_rolling_average_empty():
    assert compute_rolling_average(pd.DataFrame()) == {}


def test_detect_anomalies_normal_data():
    # Uniform data — no anomalies expected
    series = pd.Series([5, 5, 5, 5, 5, 5, 5], index=pd.date_range("2025-01-01", periods=7))
    anomalies = detect_anomalies_zscore(series, threshold=2.0)
    assert anomalies == []


def test_detect_anomalies_spike():
    # One extreme spike
    values = [5, 5, 5, 5, 5, 5, 100]
    index = pd.date_range("2025-01-01", periods=7)
    series = pd.Series(values, index=index)
    anomalies = detect_anomalies_zscore(series, threshold=2.0)
    assert len(anomalies) == 1
    assert "2025-01-07" in anomalies


def test_sentiment_slope_positive_trend():
    """Increasing negative feedback should yield positive slope."""
    now = datetime.utcnow()
    rows = []
    for i in range(30):
        # Gradually increasing negatives
        for _ in range(i):
            rows.append({"created_at": now - timedelta(days=30 - i), "sentiment": "negative", "category": "technical", "priority": "high", "source": "api"})
    df = pd.DataFrame(rows)
    slope = compute_sentiment_trend(df)
    assert slope is not None
    assert slope > 0


def test_sentiment_slope_insufficient_data():
    df = _make_df(2)  # Only 2 days — not enough
    slope = compute_sentiment_trend(df, lookback_days=3)
    assert slope is None


def test_category_shift_detects_increase():
    now = datetime.utcnow()
    rows = []
    # Prior 7 days: mostly "general"
    for i in range(7, 14):
        for _ in range(10):
            rows.append({"created_at": now - timedelta(days=i), "sentiment": "negative", "category": "general", "priority": "low", "source": "web"})
        for _ in range(1):
            rows.append({"created_at": now - timedelta(days=i), "sentiment": "negative", "category": "billing", "priority": "low", "source": "web"})
    # Recent 7 days: billing spikes
    for i in range(0, 7):
        for _ in range(2):
            rows.append({"created_at": now - timedelta(days=i), "sentiment": "negative", "category": "general", "priority": "low", "source": "web"})
        for _ in range(8):
            rows.append({"created_at": now - timedelta(days=i), "sentiment": "negative", "category": "billing", "priority": "high", "source": "web"})

    df = pd.DataFrame(rows)
    shifts = detect_category_shift(df, lookback=14, change_threshold=0.20)
    categories_shifted = [s["category"] for s in shifts]
    assert "billing" in categories_shifted


def test_full_trend_report_keys():
    df = _make_df(30)
    report = full_trend_report(df)
    for key in ("rolling_average", "anomaly_dates", "sentiment_slope", "category_shifts", "trend_status"):
        assert key in report


# ---------------------------------------------------------------------------
# LLM service
# ---------------------------------------------------------------------------

def test_llm_service_not_available_without_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from importlib import reload
    from app.services import llm_service
    reload(llm_service)
    assert llm_service.is_available() is False


def test_llm_service_available_with_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    from importlib import reload
    from app.services import llm_service
    reload(llm_service)
    assert llm_service.is_available() is True


def test_llm_service_normalises_bad_label(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"sentiment":"NEGATIVE","sentiment_confidence":0.9,"category":"unknown_cat","category_confidence":0.7,"summary":"App crashes."}'

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        from app.services.llm_service import analyze_feedback
        result = analyze_feedback("The app crashes all the time")

    assert result["sentiment"] == "negative"     # NEGATIVE → negative
    assert result["category"] == "general"       # unknown_cat → general (fallback)
    assert result["summary"] == "App crashes."


# ---------------------------------------------------------------------------
# Web scraper (mocked httpx)
# ---------------------------------------------------------------------------

def test_web_scraper_extracts_text():
    from app.services.scrapers.web_scraper import scrape_url

    fake_html = "<html><body><p>Great product, love it!</p><p>Awful experience, broken.</p></body></html>"

    with patch("httpx.get") as mock_get:
        mock_get.return_value.text = fake_html
        mock_get.return_value.raise_for_status = lambda: None
        items = scrape_url("https://example.com", css_selector="p", min_length=5)

    assert len(items) == 2
    assert all(i["source"] == "web_scrape" for i in items)
    assert any("Great product" in i["text"] for i in items)
