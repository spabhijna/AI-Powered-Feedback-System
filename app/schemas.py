from pydantic import BaseModel

class FeedbackCreate(BaseModel):
    text: str

class Feedback(BaseModel):
    id: int
    text: str
    sentiment: str
    category: str
    priority: str



