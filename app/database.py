import os
from tortoise import Tortoise


async def init_db():
    # Get database URL from environment variable, fallback to SQLite for development
    db_url = os.getenv("DATABASE_URL", "sqlite://feedback.db")
    
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["app.models"]},
        _create_db=True,
    )
    await Tortoise.generate_schemas()


async def close_db():
    await Tortoise.close_connections()
