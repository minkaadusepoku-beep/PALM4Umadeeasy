import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite+aiosqlite:///./palm4u.db"
)

_is_sqlite = "sqlite" in SQLALCHEMY_DATABASE_URL

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    **({} if _is_sqlite else {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
