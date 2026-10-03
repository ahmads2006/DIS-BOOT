"""
ByteDaily Database Client — Independent asyncpg connection pool.

Creates and manages its OWN asyncpg pool, completely separate from the
legacy pool in legacy/core/database.py. Both pools connect to the same
DATABASE_URL (Supabase PostgreSQL) but do NOT share pool objects.

Design:
  - Mirror the pattern of legacy DatabaseLayer but scoped to ByteDaily tables.
  - All repository modules access the DB through this client's singleton `bd_db`.
  - No in-memory fallback (unlike legacy) — ByteDaily requires the DB to function.

Lifecycle (managed by ByteDailyCog):
  - bd_db.initialize()  →  called in cog_load()
  - bd_db.close()       →  called in cog_unload()
"""

from typing import Any, Dict, List, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

from config import DATABASE_URL
from bridge.legacy_adapter import log


class ByteDailyDB:
    """
    Manages an independent asyncpg connection pool for ByteDaily features.
    Provides convenience query wrappers converting record rows into standard dicts.
    """

    def __init__(self) -> None:
        self.pool: Optional[Any] = None
        self.is_connected: bool = False

    async def initialize(self) -> None:
        if not DATABASE_URL:
            log.error("ByteDaily: DATABASE_URL not set — cannot initialize BD pool.")
            return

        if not asyncpg:
            log.error("ByteDaily: asyncpg is not installed — cannot initialize BD pool.")
            return

        try:
            self.pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=3,
                timeout=10,
                command_timeout=10,
                statement_cache_size=0,
            )
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            self.is_connected = True
            log.info("ByteDaily: DB pool initialized.")
        except Exception as e:
            self.is_connected = False
            log.error(f"ByteDaily: Failed to initialize DB pool: {e}")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
            self.is_connected = False
            log.info("ByteDaily: DB pool closed.")

    def acquire(self):
        """Context manager: async with bd_db.acquire() as conn: ..."""
        if not self.pool:
            raise RuntimeError("ByteDaily database pool is not initialized.")
        return self.pool.acquire()

    async def execute(self, query: str, *args: Any) -> str:
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        async with self.acquire() as conn:
            records = await conn.fetch(query, *args)
            return [dict(r) for r in records]

    async def fetchrow(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        async with self.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetchval(self, query: str, *args: Any) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)


# Module-level singleton — imported by all repository modules
bd_db = ByteDailyDB()
