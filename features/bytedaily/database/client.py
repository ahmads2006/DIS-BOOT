"""
ByteDaily Database Client — uses the shared asyncpg pool (see db_pool.py).

All repository modules access the DB through the singleton `bd_db`.
No in-memory fallback — ByteDaily requires the DB to function.

Lifecycle (managed by ByteDailyCog):
  - bd_db.initialize()  →  called in cog_load (refs shared pool)
  - bd_db.close()       →  called in cog_unload (releases shared pool ref)
"""

from typing import Any, Dict, List, Optional

import db_pool
from bridge.legacy_adapter import log


class ByteDailyDB:
    """
    ByteDaily query wrappers over the shared asyncpg pool.
    """

    def __init__(self) -> None:
        self.pool: Optional[Any] = None
        self.is_connected: bool = False

    async def initialize(self) -> None:
        try:
            self.pool = await db_pool.initialize()
            self.is_connected = self.pool is not None
            if self.is_connected:
                log.info("ByteDaily: Attached to shared DB pool.")
            else:
                log.error("ByteDaily: Shared DB pool unavailable — ByteDaily requires DATABASE_URL.")
        except Exception as e:
            self.is_connected = False
            self.pool = None
            log.error(f"ByteDaily: Failed to attach to shared DB pool: {e}")

    async def close(self) -> None:
        if self.pool is not None:
            await db_pool.release()
            self.pool = None
            self.is_connected = False
            log.info("ByteDaily: Released shared DB pool reference.")

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
