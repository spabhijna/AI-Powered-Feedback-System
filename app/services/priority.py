def priority_scoring(text: str, sentiment:str):
    if sentiment == 'negative' and ('urgent' in text or 'not working' in text):
        return 'high'
    elif sentiment == 'negative':
        return 'moderate'
    else:
        return 'low'
