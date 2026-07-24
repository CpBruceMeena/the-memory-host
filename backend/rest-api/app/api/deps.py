"""FastAPI dependency injection — provides database sessions."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: provide an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Type aliases for convenience ─────────────────────────────

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
