from app.services.categorizer import categorize
from app.services.sentiment import analyze_sentiment
from app.services.priority import priority_scoring

def process_feedback(text: str):
    sentiment = analyze_sentiment(text=text)
    category = categorize(text=text)
    priority = priority_scoring(text=text, sentiment=sentiment)

    return sentiment, category, priority