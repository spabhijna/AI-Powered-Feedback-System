def categorize(text: str):
    text = text.lower()

    if "payment" in text or "price" in text:
        return "billing"
    elif "bug" in text or "error" in text:
        return "technical"
    elif "slow" in text or "delay" in text:
        return "performance"
    else:
        return "general"