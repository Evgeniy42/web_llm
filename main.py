from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.configuration.database import engine

from app.presentation_layer.routers import HealthRouter, UserRouter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: проверяем подключение к БД
    with engine.connect() as conn:
        pass
    yield
    # shutdown: закрываем пул соединений
    engine.dispose()


app = FastAPI(title="Web LLM", lifespan=lifespan)

app.include_router(HealthRouter)
app.include_router(UserRouter)
