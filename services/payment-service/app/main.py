from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.database import Base, sync_engin
import app.models.payment



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=sync_engin)
    yield



app = FastAPI(
    title='NEXUS — Payment Microservice',
    description='High-concurrency, idempotent payment processing service built with FastAPI and SQLAlchemy.',
    version='1.0.0',
    lifespan=lifespan,
)



@app.get('/health', tags=['health'])
async def health_check() -> dict[str, str]:
    return {'status': 'healthy', 'service': 'payment-service'}