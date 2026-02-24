"""Sentiment analysis service - wrapper around transformer model"""

from app.services.sentiment_model import (
    analyze_sentiment as model_analyze_sentiment,
    analyze_sentiment_with_confidence,
)


def analyze_sentiment(text: str) -> str:
    """Analyze sentiment using transformer model (backward compatible)"""
    return model_analyze_sentiment(text)


def analyze_sentiment_detailed(text: str) -> tuple[str, float]:
    """Analyze sentiment with confidence score for internal use"""
    return analyze_sentiment_with_confidence(text)
