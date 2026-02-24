def handle_alert(feedback):
    """
    Centralized alert handling for feedback.
    Currently console-based, but structured for future extension.
    """
    if feedback.priority == "high":
        print(f"🚨 HIGH PRIORITY ALERT")
        print(f"   Category: {feedback.category}")
        print(f"   Sentiment: {feedback.sentiment}")
        print(f"   Source: {feedback.source}")
        print(f"   Text: {feedback.text[:100]}...")
        print(f"   ID: {feedback.id}")
        print()
