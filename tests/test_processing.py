"""
Unit tests for processing pipeline services.
All external model calls are mocked.
"""

from unittest.mock import patch


# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------

from app.services.priority import priority_scoring


def test_priority_high_urgent_keyword():
    score = priority_scoring(
        text="This is urgent, the system is down!",
        sentiment="negative",
        sentiment_confidence=0.95,
        category="technical",
        category_confidence=0.9,
    )
    assert score == "high"


def test_priority_low_positive():
    score = priority_scoring(
        text="Everything is working great.",
        sentiment="positive",
        sentiment_confidence=0.92,
        category="general",
        category_confidence=0.85,
    )
    assert score == "low"


def test_priority_moderate_negative_medium_confidence():
    score = priority_scoring(
        text="The app is slow sometimes.  It is not working properly.",
        sentiment="negative",
        sentiment_confidence=0.75,
        category="performance",
        category_confidence=0.70,
    )
    # negative (conf 0.75) → +2, "not working" → +2 = score 4 → moderate
    assert score in ("moderate", "high")


# ---------------------------------------------------------------------------
# Processing pipeline (mocked models)
# ---------------------------------------------------------------------------

def test_process_feedback_returns_four_tuple():
    with (
        patch("app.services.llm_service.is_available", return_value=True),
        patch("app.services.llm_service.analyze_feedback", return_value={
            "sentiment": "negative",
            "sentiment_confidence": 0.91,
            "category": "technical",
            "category_confidence": 0.85,
            "summary": "Login button is broken.",
        }),
    ):
        from app.services.processing import process_feedback

        result = process_feedback("The login button is broken")

    assert len(result) == 4
    sentiment, category, priority, summary = result
    assert sentiment == "negative"
    assert category == "technical"
    assert priority in ("high", "moderate", "low")
    assert summary == "Login button is broken."


def test_process_feedback_positive():
    with (
        patch("app.services.llm_service.is_available", return_value=True),
        patch("app.services.llm_service.analyze_feedback", return_value={
            "sentiment": "positive",
            "sentiment_confidence": 0.96,
            "category": "general",
            "category_confidence": 0.80,
            "summary": "User loves the product.",
        }),
    ):
        from app.services.processing import process_feedback

        sentiment, category, priority, _ = process_feedback("Love this product!")

    assert sentiment == "positive"
    assert priority == "low"


# ---------------------------------------------------------------------------
# Category list includes feature_request
# ---------------------------------------------------------------------------

def test_categories_include_feature_request():
    from app.services.category_model import CATEGORIES

    assert "feature_request" in CATEGORIES


def test_categories_include_all_expected():
    from app.services.category_model import CATEGORIES

    for expected in ("billing", "technical", "performance", "general", "feature_request"):
        assert expected in CATEGORIES, f"Missing category: {expected}"
