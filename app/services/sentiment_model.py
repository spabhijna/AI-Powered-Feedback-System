"""
Sentiment analysis using HuggingFace transformers.
Model loads once at module import time.
"""

from transformers import pipeline

print("🤖 Loading sentiment analysis model...")

# Load model once at module level (not per-request)
# Uses distilbert-base-uncased-finetuned-sst-2-english by default
sentiment_pipeline = pipeline(
    "sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english"
)

print("✅ Sentiment model loaded successfully")


def analyze_sentiment_with_confidence(text: str) -> tuple[str, float]:
    """
    Analyze sentiment using transformer model.

    Args:
        text: Input feedback text

    Returns:
        tuple: (sentiment_label, confidence_score)
        - sentiment_label: "positive", "negative", or "neutral"
        - confidence_score: float between 0 and 1
    """
    # Truncate text to avoid model limitations (512 tokens)
    text = text[:500]

    result = sentiment_pipeline(text)[0]

    label = result["label"]  # POSITIVE or NEGATIVE
    score = result["score"]  # confidence

    # Normalize labels to our format
    if label.upper() == "POSITIVE":
        return "positive", score
    elif label.upper() == "NEGATIVE":
        return "negative", score
    else:
        # Model rarely returns neutral, but handle it
        return "neutral", score


def analyze_sentiment(text: str) -> str:
    """
    Backward-compatible wrapper that returns only the label.

    Args:
        text: Input feedback text

    Returns:
        str: "positive", "negative", or "neutral"
    """
    sentiment, _ = analyze_sentiment_with_confidence(text)
    return sentiment
