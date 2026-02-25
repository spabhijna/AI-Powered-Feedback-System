import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise
from app.api.routes import router
import logging

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    from app.services import llm_service
    from app.services.scheduler import start_scheduler, stop_scheduler, load_db_jobs_on_startup
    from tortoise import Tortoise

    # Wait for Tortoise to be initialized by register_tortoise
    # This ensures DB is ready before scheduler starts
    logger.info("Waiting for database initialization...")
    # Database is initialized by register_tortoise() call below
    # Just verify it's accessible
    try:
        from app.models import ScraperConfig
        # Quick test query to ensure DB is ready
        await ScraperConfig.all().count()
        logger.info("✅ Database connection verified")
    except Exception as exc:
        logger.warning("Database not yet ready on lifespan start: %s", exc)

    if llm_service.is_available():
        print("🚀 GROQ_API_KEY found — using Groq LLM for analysis")
    else:
        print("⚠️  GROQ_API_KEY not set — loading local transformer models (fallback)...")
        from app.services import sentiment_model, category_model  # noqa: F401
        print("✅ Local models loaded")

    start_scheduler()
    await load_db_jobs_on_startup()
    yield
    stop_scheduler()
    logger.info("Shutting down...")


app = FastAPI(lifespan=lifespan)


# Get CORS origins from environment variable
cors_origins = os.getenv("CORS_ORIGINS", "*")
if cors_origins == "*":
    cors_origins_list = ["*"]
else:
    cors_origins_list = [origin.strip() for origin in cors_origins.split(",")]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=router)

# Register Tortoise ORM with FastAPI
# This is called during app initialization, before lifespan startup
register_tortoise(
    app,
    db_url=os.getenv("DATABASE_URL", "sqlite://feedback.db"),
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)


@app.get("/")
async def root():
    return {"message": "Welcome to Feedback System API", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    return {
        "status": "healthy",
        "database": "sqlite",
        "environment": os.getenv("ENV", "development")
    }
