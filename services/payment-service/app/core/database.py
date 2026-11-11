from collections.abc import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings



class Base(DeclarativeBase):
    pass



# Async Engine for FastAPI Endpoints
async_engin = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engin,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Sync Engine for Pika RabbitMQ Worker & Table Initialization
sync_engin = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engin,
    autocommit=False,
    autoflush=False,
)



async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
