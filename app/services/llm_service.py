"""
Groq LLM service for feedback analysis.

Replaces the heavy local DistilBERT + BART pipeline (~1.8 GB) with a single
Groq API call to llama-3.3-70b-versatile (~400 ms, no GPU required).

Environment variables:
    GROQ_API_KEY  – required for Groq path
    GROQ_MODEL    – defaults to "llama-3.3-70b-versatile"
    LOCAL_FALLBACK – set to "true" to use local models when Groq fails
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """You are a customer feedback analysis assistant.
Analyse the given feedback text and return a JSON object with exactly these fields:
{
  "sentiment": "positive" | "negative" | "neutral",
  "sentiment_confidence": <float 0-1>,
  "category": "billing" | "technical" | "performance" | "general" | "feature_request",
  "category_confidence": <float 0-1>,
  "summary": "<one concise sentence summarising the feedback>"
}
Return ONLY the JSON object. No markdown fences, no explanation."""

VALID_SENTIMENTS = {"positive", "negative", "neutral"}
VALID_CATEGORIES = {"billing", "technical", "performance", "general", "feature_request"}


def _get_client():
    """Lazily create a Groq client (avoids import error when key is absent)."""
    from groq import Groq  # type: ignore

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    return Groq(api_key=api_key)


def analyze_feedback(text: str) -> dict:
    """
    Analyse a single feedback text using the Groq LLM.

    Returns:
        dict with keys: sentiment, sentiment_confidence,
                        category, category_confidence, summary

    Raises:
        Exception – propagated so the caller can decide on fallback strategy.
    """
    client = _get_client()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Feedback: {text[:1000]}"},
        ],
        temperature=0.1,
        max_tokens=256,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    result = json.loads(raw)

    # Normalise and validate
    sentiment = result.get("sentiment", "neutral").lower()
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "neutral"

    category = result.get("category", "general").lower()
    if category not in VALID_CATEGORIES:
        category = "general"

    sentiment_conf = float(result.get("sentiment_confidence", 0.8))
    category_conf = float(result.get("category_confidence", 0.8))
    summary: Optional[str] = result.get("summary")

    return {
        "sentiment": sentiment,
        "sentiment_confidence": min(max(sentiment_conf, 0.0), 1.0),
        "category": category,
        "category_confidence": min(max(category_conf, 0.0), 1.0),
        "summary": summary,
    }


def is_available() -> bool:
    """Return True if a Groq API key is configured."""
    return bool(os.getenv("GROQ_API_KEY"))
