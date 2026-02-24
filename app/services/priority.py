def priority_scoring(
    text: str,
    sentiment: str,
    sentiment_confidence: float,
    category: str,
    category_confidence: float,
) -> str:
    """Intelligent priority scoring using ML confidence and keywords"""
    score = 0
    text_lower = text.lower()

    # Sentiment impact with confidence weighting
    if sentiment == "negative":
        if sentiment_confidence > 0.9:
            score += 3  # High confidence negative
        elif sentiment_confidence > 0.7:
            score += 2  # Medium confidence negative
        else:
            score += 1  # Low confidence negative

    # Penalize low confidence predictions
    if sentiment_confidence < 0.6:
        score -= 1

    # Keyword boosters (still useful for urgency signals)
    if "urgent" in text_lower:
        score += 3
    if "not working" in text_lower:
        score += 2
    if "critical" in text_lower:
        score += 3
    if "broken" in text_lower:
        score += 2

    # Category-specific adjustments
    if category == "billing" and ("refund" in text_lower or "charged" in text_lower):
        score += 2
    if category == "technical" and category_confidence > 0.8:
        score += 1

    # Map score to priority levels
    if score >= 5:
        return "high"
    elif score >= 3:
        return "moderate"
    else:
        return "low"
