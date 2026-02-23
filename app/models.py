from tortoise import fields
from tortoise.models import Model

class Feedback(Model):
    id = fields.IntField(pk=True)
    text = fields.TextField()
    sentiment = fields.CharField(max_length=20)
    category = fields.CharField(max_length=50)
    priority = fields.CharField(max_length=20)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "feedback"