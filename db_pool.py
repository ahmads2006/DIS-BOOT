"""
Shared asyncpg connection pool adapter (re-exports from database.connection).
Maintains full backward-compatibility for legacy and feature modules.
"""

from database.connection import (
    get_pool,
    get_pool_stats,
    initialize,
    monitor_db_pool,
    release,
    run_pending_migrations,
    verify_connectivity,
)

__all__ = [
    "initialize",
    "release",
    "get_pool",
    "get_pool_stats",
    "verify_connectivity",
    "monitor_db_pool",
    "run_pending_migrations",
]

