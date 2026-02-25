import os
import logging
from app.services.priority import priority_scoring

logger = logging.getLogger(__name__)

USE_LOCAL = os.getenv("LOCAL_FALLBACK", "false").lower() == "true"


def _local_process(text: str) -> tuple[str, str, str, None]:
    """Fallback: run the original local DistilBERT + BART pipeline."""
    from app.services.categorizer import categorize_detailed
    from app.services.sentiment import analyze_sentiment_detailed

    sentiment, sentiment_conf = analyze_sentiment_detailed(text=text)
    category, category_conf = categorize_detailed(text=text)
    priority = priority_scoring(
        text=text,
        sentiment=sentiment,
        sentiment_confidence=sentiment_conf,
        category=category,
        category_confidence=category_conf,
    )
    return sentiment, category, priority, None


def process_feedback(text: str) -> tuple[str, str, str, str | None]:
    """
    Process feedback through AI pipeline.

    Tries Groq LLM first (fast, <1 s).  Falls back to the local transformer
    models if GROQ_API_KEY is absent, Groq is unavailable, or LOCAL_FALLBACK
    env var is set to "true".

    Returns (sentiment, category, priority, summary).
    """
    from app.services import llm_service

    if not USE_LOCAL and llm_service.is_available():
        try:
            result = llm_service.analyze_feedback(text)
            priority = priority_scoring(
                text=text,
                sentiment=result["sentiment"],
                sentiment_confidence=result["sentiment_confidence"],
                category=result["category"],
                category_confidence=result["category_confidence"],
            )
            return result["sentiment"], result["category"], priority, result["summary"]
        except Exception as exc:
            logger.warning("Groq unavailable (%s) — falling back to local models", exc)

    return _local_process(text)
