from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FeedbackCreate(BaseModel):
    text: str
    source: str = "web"


class Feedback(BaseModel):
    id: int
    text: str
    sentiment: str
    category: str
    priority: str
    source: str
    summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
