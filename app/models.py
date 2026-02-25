from tortoise import fields
from tortoise.models import Model


class Feedback(Model):
    id = fields.IntField(pk=True)
    text = fields.TextField()
    sentiment = fields.CharField(max_length=20)
    category = fields.CharField(max_length=60)
    priority = fields.CharField(max_length=20)
    source = fields.CharField(max_length=30, default="web")
    summary = fields.TextField(null=True)
    app_id = fields.CharField(max_length=100, null=True)
    store_country = fields.CharField(max_length=10, null=True)
    # Enriched fields populated by scrapers
    external_id = fields.CharField(max_length=200, null=True)  # Play/App Store review ID for dedup
    rating = fields.IntField(null=True)                        # Star rating 1-5
    reviewed_at = fields.DatetimeField(null=True)              # Original review timestamp
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "feedback"


class Alert(Model):
    id = fields.IntField(pk=True)
    type = fields.CharField(max_length=50)
    severity = fields.CharField(max_length=20)
    message = fields.TextField()
    triggered_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "alert"


class ScraperConfig(Model):
    """Persisted scraper configuration managed from the dashboard."""
    id = fields.IntField(pk=True)
    source_type = fields.CharField(max_length=20)   # "google_play" | "app_store" | "web"
    app_id = fields.CharField(max_length=200, null=True)   # package name or numeric ID
    app_name = fields.CharField(max_length=200, null=True) # App Store slug
    country = fields.CharField(max_length=10, default="us")
    count = fields.IntField(default=50)
    interval_hours = fields.IntField(default=6)
    enabled = fields.BooleanField(default=True)
    label = fields.CharField(max_length=100, null=True)    # friendly display name
    last_run_at = fields.DatetimeField(null=True)
    last_run_count = fields.IntField(null=True)
    last_status = fields.CharField(max_length=20, default="idle")  # "idle", "running", "success", "error"
    last_error = fields.TextField(null=True)               # Error message from last failed run
    retry_count = fields.IntField(default=0)               # Consecutive failure count
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "scraper_config"
