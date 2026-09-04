from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine_kwargs = {"echo": settings.LOG_SQL if hasattr(settings, "LOG_SQL") else False}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
'''
        # Migrate: add model_key to training_history if missing
        from sqlalchemy import inspect, text
        def _migrate(conn_sync):
            inspector = inspect(conn_sync)
            cols = [c["name"] for c in inspector.get_columns("training_history")]
            if "model_key" not in cols:
                conn_sync.execute(text("ALTER TABLE training_history ADD COLUMN model_key VARCHAR"))
                import logging
                logging.getLogger(__name__).info("Added model_key column to training_history")
        await conn.run_sync(_migrate)
'''