from app.services.categorizer import categorize_detailed
from app.services.sentiment import analyze_sentiment_detailed
from app.services.priority import priority_scoring


def process_feedback(text: str) -> tuple[str, str, str]:
    """
    Process feedback through AI pipeline.
    Uses confidence scores internally for intelligent priority scoring.
    Returns simple labels for backward compatibility.
    """
    # Get predictions with confidence scores
    sentiment, sentiment_conf = analyze_sentiment_detailed(text=text)
    category, category_conf = categorize_detailed(text=text)

    # Intelligent priority scoring using confidence
    priority = priority_scoring(
        text=text,
        sentiment=sentiment,
        sentiment_confidence=sentiment_conf,
        category=category,
        category_confidence=category_conf,
    )

    return sentiment, category, priority
