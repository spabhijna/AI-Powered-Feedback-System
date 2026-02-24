from pydantic import BaseModel
from datetime import datetime


class FeedbackCreate(BaseModel):
    text: str


class Feedback(BaseModel):
    id: int
    text: str
    sentiment: str
    category: str
    priority: str
    source: str
    created_at: datetime

    class Config:
        from_attributes = True
