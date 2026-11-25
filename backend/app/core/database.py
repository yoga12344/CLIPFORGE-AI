from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
from typing import AsyncGenerator
from .config import settings

# Create async SQLite engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async_session_factory = AsyncSessionLocal

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db() -> None:
    """Initialize database tables and run safe column additions."""
    # Import all models to register metadata
    from ..db import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.run_sync(Base.metadata.create_all)
        
        # Check existing columns in transcripts table for non-destructive migration
        try:
            res = await conn.execute(text("PRAGMA table_info(transcripts)"))
            cols = [row[1] for row in res.fetchall()]
            if "status" not in cols:
                await conn.execute(text("ALTER TABLE transcripts ADD COLUMN status VARCHAR(50) DEFAULT 'completed'"))
            if "task_type" not in cols:
                await conn.execute(text("ALTER TABLE transcripts ADD COLUMN task_type VARCHAR(50) DEFAULT 'transcribe'"))
            if "device_used" not in cols:
                await conn.execute(text("ALTER TABLE transcripts ADD COLUMN device_used VARCHAR(50)"))
            if "processing_duration_seconds" not in cols:
                await conn.execute(text("ALTER TABLE transcripts ADD COLUMN processing_duration_seconds FLOAT"))
            if "updated_at" not in cols:
                await conn.execute(text("ALTER TABLE transcripts ADD COLUMN updated_at DATETIME"))
        except Exception:
            pass

        # Check existing columns in speakers table for non-destructive migration
        try:
            res = await conn.execute(text("PRAGMA table_info(speakers)"))
            cols = [row[1] for row in res.fetchall()]
            if "analysis_id" not in cols:
                await conn.execute(text("ALTER TABLE speakers ADD COLUMN analysis_id VARCHAR(36)"))
            if "speaker_identifier" not in cols:
                await conn.execute(text("ALTER TABLE speakers ADD COLUMN speaker_identifier VARCHAR(50)"))
            if "display_name" not in cols:
                await conn.execute(text("ALTER TABLE speakers ADD COLUMN display_name VARCHAR(100)"))
            if "total_speech_duration" not in cols:
                await conn.execute(text("ALTER TABLE speakers ADD COLUMN total_speech_duration FLOAT DEFAULT 0.0"))
            if "turn_count" not in cols:
                await conn.execute(text("ALTER TABLE speakers ADD COLUMN turn_count INTEGER DEFAULT 0"))
            if "model_name" not in cols:
                await conn.execute(text("ALTER TABLE speakers ADD COLUMN model_name VARCHAR(100) DEFAULT '3dspeaker_campplus'"))
            if "model_version" not in cols:
                await conn.execute(text("ALTER TABLE speakers ADD COLUMN model_version VARCHAR(50) DEFAULT '1.0.0'"))
            if "updated_at" not in cols:
                await conn.execute(text("ALTER TABLE speakers ADD COLUMN updated_at DATETIME"))
        except Exception:
            pass
