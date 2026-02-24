import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import register_tortoise
from app.api.routes import router

# Load environment variables from .env file
load_dotenv()

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    """Load ML models at startup to avoid first-request delay"""
    print("🚀 Starting up - loading AI models...")
    
    # Import models to trigger loading (happens once at module level)
    from app.services import sentiment_model, category_model

    print("✨ All models loaded - ready to process feedback!")


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
register_tortoise(
    app,
    db_url=os.getenv("DATABASE_URL", "sqlite://feedback.db"),
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

# Mount static files for dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")


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
