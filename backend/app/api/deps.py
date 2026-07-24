"""FastAPI dependency injection — provides database sessions and cache."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import GameCache, cache
from app.core.config import settings
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


def get_cache() -> GameCache:
    """Dependency: provide the cache singleton."""
    return cache


# ── Type aliases for convenience ─────────────────────────────

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CacheDep = Annotated[GameCache, Depends(get_cache)]


def get_client_host(request: Request) -> str:
    """Extract the client's host from the request."""
    if forwarded := request.headers.get("X-Forwarded-For"):
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
