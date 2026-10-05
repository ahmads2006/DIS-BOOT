"""
Shared asyncpg connection pool for legacy exam DB and ByteDaily (Supabase).

Both subsystems acquire the same pool via initialize()/release() reference counting
so total connections stay within Supabase limits.
"""

from typing import Any, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

from config import DATABASE_URL
from bridge.legacy_adapter import log

_POOL: Optional[Any] = None
_REF_COUNT: int = 0

# Single cap for legacy + ByteDaily (formerly 5 + 3 separate pools).
_POOL_MIN_SIZE = 1
_POOL_MAX_SIZE = 6
_POOL_TIMEOUT = 10
_COMMAND_TIMEOUT = 10


async def initialize() -> Optional[Any]:
    """
    Return the shared pool, creating it on first use.
    Call once per subsystem at startup (legacy + ByteDaily each call initialize).
    """
    global _POOL, _REF_COUNT

    if _POOL is not None:
        _REF_COUNT += 1
        return _POOL

    if not DATABASE_URL:
        log.warning("Shared DB pool: DATABASE_URL not set — pool unavailable.")
        return None

    if not asyncpg:
        log.warning("Shared DB pool: asyncpg not installed — pool unavailable.")
        return None

    try:
        _POOL = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=_POOL_MIN_SIZE,
            max_size=_POOL_MAX_SIZE,
            timeout=_POOL_TIMEOUT,
            command_timeout=_COMMAND_TIMEOUT,
            statement_cache_size=0,
        )
        async with _POOL.acquire() as conn:
            await conn.fetchval("SELECT 1")
        _REF_COUNT = 1
        log.info(
            f"Shared DB pool initialized (max_size={_POOL_MAX_SIZE})."
        )
        return _POOL
    except Exception as e:
        _POOL = None
        _REF_COUNT = 0
        log.error(f"Shared DB pool: failed to initialize: {e}")
        return None


async def release() -> None:
    """Decrement refcount; close the pool when no subsystems hold it."""
    global _POOL, _REF_COUNT

    if _REF_COUNT <= 0:
        return

    _REF_COUNT -= 1
    if _REF_COUNT > 0:
        return

    if _POOL is not None:
        await _POOL.close()
        _POOL = None
        log.info("Shared DB pool closed.")


def get_pool() -> Optional[Any]:
    """Return the live pool or None if not initialized."""
    return _POOL
