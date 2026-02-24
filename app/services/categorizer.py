"""Category classification service - wrapper around zero-shot model"""

from app.services.category_model import (
    categorize as model_categorize,
    categorize_with_confidence,
)


def categorize(text: str) -> str:
    """Categorize feedback using zero-shot classification (backward compatible)"""
    return model_categorize(text)


def categorize_detailed(text: str) -> tuple[str, float]:
    """Categorize with confidence score for internal use"""
    return categorize_with_confidence(text)
