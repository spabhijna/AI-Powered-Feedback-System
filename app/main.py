from fastapi import FastAPI
from app.api.routes import router
from tortoise.contrib.fastapi import register_tortoise

app = FastAPI()

register_tortoise(
    app,
    db_url='sqlite://feedback.db',
    modules={'models': ['app.models']},
    generate_schemas=True,
    add_exception_handlers=True,
)

app.include_router(router=router)

@app.get("/")
async def root():
    return {"message": "Welcome to Feedback System API", "docs": "/docs"}