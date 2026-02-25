"""
Category classification using zero-shot learning.
Model loads once at module import time.
"""

from transformers import pipeline

print("🤖 Loading category classification model...")

# Load zero-shot classification model once at module level
# Uses facebook/bart-large-mnli for zero-shot classification
category_pipeline = pipeline(
    "zero-shot-classification", model="facebook/bart-large-mnli"
)

print("✅ Category model loaded successfully")

# Define our categories
CATEGORIES = ["billing", "technical", "performance", "general", "feature_request"]


def categorize_with_confidence(text: str) -> tuple[str, float]:
    """
    Categorize feedback using zero-shot classification.

    Args:
        text: Input feedback text

    Returns:
        tuple: (category_label, confidence_score)
        - category_label: "billing", "technical", "performance", or "general"
        - confidence_score: float between 0 and 1
    """
    # Truncate text to avoid model limitations
    text = text[:500]

    result = category_pipeline(text, CATEGORIES)

    # Get top prediction
    top_label = result["labels"][0]
    top_score = result["scores"][0]

    return top_label, top_score


def categorize(text: str) -> str:
    """
    Backward-compatible wrapper that returns only the category label.

    Args:
        text: Input feedback text

    Returns:
        str: "billing", "technical", "performance", or "general"
    """
    category, _ = categorize_with_confidence(text)
    return category
