from fastapi import APIRouter
from app.schemas import FeedbackCreate
from app.models import Feedback
from app.services.processing import process_feedback

router = APIRouter()

@router.post("/feedback")
async def create_feedback(data: FeedbackCreate):
    sentiment, category, priority = process_feedback(data.text)

    feedback = await Feedback.create(
        text=data.text,
        sentiment=sentiment,
        category=category,
        priority=priority
    )

    return feedback

@router.get("/feedback")
async def get_feedback():
    return await Feedback.all()