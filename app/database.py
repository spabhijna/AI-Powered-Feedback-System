from tortoise import Tortoise

async def init_db():
    await Tortoise.init(
        db_url='sqlite://feedback.db',
        modules={'models': ['app.models']},
        _create_db=True
    )
    await Tortoise.generate_schemas()

async def close_db():
    await Tortoise.close_connections()