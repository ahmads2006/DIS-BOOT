"""
Asyncpg Database Connection Pool, Health Checks & Migration Runner.

Features:
  - Shared connection pool with reference counting to stay within Supabase limits.
  - Lightweight background health monitor running every 60 seconds.
  - Alerts when pool utilization exceeds 80% capacity.
  - Detection of acquisition and query timeouts.
  - Automatic migration runner verifying and applying pending SQL schema changes.
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

from config import DATABASE_URL
from core.logging import log, measure_duration
from core.sentry import capture_exception

_POOL: Optional[Any] = None
_REF_COUNT: int = 0
_MONITOR_TASK: Optional[asyncio.Task] = None

_POOL_MIN_SIZE = 1
_POOL_MAX_SIZE = 6
_POOL_TIMEOUT = 10.0
_COMMAND_TIMEOUT = 10.0
_HEALTH_CHECK_INTERVAL = 60.0
_UTILIZATION_ALERT_THRESHOLD = 0.80  # 80%


async def initialize() -> Optional[Any]:
    """Return the shared pool, creating it on first use with ref counting."""
    global _POOL, _REF_COUNT

    if _POOL is not None:
        _REF_COUNT += 1
        return _POOL

    if not DATABASE_URL:
        log.warning("Database connection: DATABASE_URL not set — pool unavailable.")
        return None

    if not asyncpg:
        log.warning("Database connection: asyncpg not installed — pool unavailable.")
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
            "Shared asyncpg connection pool initialized",
            min_size=_POOL_MIN_SIZE,
            max_size=_POOL_MAX_SIZE,
        )
        start_pool_monitor()
        return _POOL
    except Exception as e:
        _POOL = None
        _REF_COUNT = 0
        log.error("Failed to initialize asyncpg connection pool", error=str(e))
        capture_exception(e, tags={"component": "database_pool_init"})
        return None


async def release() -> None:
    """Decrement refcount; close the pool and stop monitor when all references are released."""
    global _POOL, _REF_COUNT

    if _REF_COUNT <= 0:
        return

    _REF_COUNT -= 1
    if _REF_COUNT > 0:
        return

    stop_pool_monitor()

    if _POOL is not None:
        try:
            await _POOL.close()
            log.info("Shared asyncpg connection pool closed successfully.")
        except Exception as e:
            log.warning("Error while closing asyncpg pool", error=str(e))
        finally:
            _POOL = None


def get_pool() -> Optional[Any]:
    """Return live pool or None."""
    return _POOL


# ─────────────────────────────────────────────────────────────────────────────
# Health Checks & Monitoring
# ─────────────────────────────────────────────────────────────────────────────

async def verify_connectivity() -> bool:
    """Verify that the database is reachable and responsive."""
    pool = get_pool()
    if not pool:
        log.warning("Database connectivity check failed: pool not initialized")
        return False

    try:
        with measure_duration("db_ping"):
            async with pool.acquire(timeout=5.0) as conn:
                val = await conn.fetchval("SELECT 1")
                return val == 1
    except asyncio.TimeoutError:
        log.error("Database connectivity check: acquisition timed out (5s)")
        capture_exception(TimeoutError("DB ping acquisition timeout"), tags={"component": "db_health"})
        return False
    except Exception as e:
        log.error("Database connectivity check failed", error=str(e))
        capture_exception(e, tags={"component": "db_health"})
        return False


def get_pool_stats() -> Dict[str, Any]:
    """Return point-in-time metrics on the connection pool."""
    pool = get_pool()
    if not pool:
        return {"status": "inactive"}

    total = pool.get_size()
    idle = pool.get_idle_size()
    min_size = pool.get_min_size()
    max_size = pool.get_max_size()
    active = total - idle
    utilization = (active / max_size) if max_size > 0 else 0.0

    return {
        "status": "active",
        "total_connections": total,
        "idle_connections": idle,
        "active_connections": active,
        "min_size": min_size,
        "max_size": max_size,
        "utilization_percent": round(utilization * 100, 2),
    }


async def monitor_db_pool() -> None:
    """Background worker running every 60s to check pool health and utilization."""
    log.info("Database pool health monitor worker started.")
    while True:
        try:
            await asyncio.sleep(_HEALTH_CHECK_INTERVAL)
            pool = get_pool()
            if not pool:
                continue

            stats = get_pool_stats()
            total = stats.get("total_connections", 0)
            idle = stats.get("idle_connections", 0)
            active = stats.get("active_connections", 0)
            max_size = stats.get("max_size", _POOL_MAX_SIZE)
            utilization_pct = stats.get("utilization_percent", 0.0)

            # High utilization alert (> 80%)
            if (active / max_size) >= _UTILIZATION_ALERT_THRESHOLD:
                log.warning(
                    "⚠️ High DB pool utilization detected!",
                    utilization=f"{utilization_pct}%",
                    active_connections=active,
                    total_connections=total,
                    idle_connections=idle,
                    max_capacity=max_size,
                )

            # Acquisition & latency health ping
            start_ping = time.perf_counter()
            try:
                async with pool.acquire(timeout=5.0) as conn:
                    await conn.fetchval("SELECT 1")
                ping_latency = round((time.perf_counter() - start_ping) * 1000, 2)

                log.debug(
                    "Database pool health check OK",
                    active=active,
                    idle=idle,
                    total=total,
                    ping_ms=ping_latency,
                )
            except asyncio.TimeoutError:
                log.error(
                    "🚨 DB pool health check ping timed out after 5.0s!",
                    active=active,
                    total=total,
                    idle=idle,
                )
                capture_exception(
                    TimeoutError("Database connection acquisition timeout"),
                    tags={"component": "db_pool_health", "active": active, "total": total},
                )
            except Exception as e:
                log.error("🚨 DB pool health check ping error", error=str(e))
                capture_exception(e, tags={"component": "db_pool_health"})

        except asyncio.CancelledError:
            log.info("Database pool health monitor worker cancelled.")
            break
        except Exception as e:
            log.warning("Unexpected error in DB pool health monitor", error=str(e))


def start_pool_monitor() -> None:
    """Start background health monitor task if not already running."""
    global _MONITOR_TASK
    if _MONITOR_TASK is None or _MONITOR_TASK.done():
        try:
            loop = asyncio.get_running_loop()
            _MONITOR_TASK = loop.create_task(monitor_db_pool(), name="db-pool-health-monitor")
        except RuntimeError:
            pass


def stop_pool_monitor() -> None:
    """Cancel background health monitor task."""
    global _MONITOR_TASK
    if _MONITOR_TASK and not _MONITOR_TASK.done():
        _MONITOR_TASK.cancel()
        _MONITOR_TASK = None


# ─────────────────────────────────────────────────────────────────────────────
# Schema Migrations
# ─────────────────────────────────────────────────────────────────────────────

async def run_pending_migrations() -> int:
    """
    Scan features/bytedaily/database/migrations for .sql files,
    verify which migrations have been applied, and execute any pending scripts.
    Returns the count of newly applied migrations.
    """
    pool = get_pool()
    if not pool:
        log.warning("Cannot run migrations: DB pool not initialized.")
        return 0

    migrations_dir = Path(__file__).parent.parent / "features" / "bytedaily" / "database" / "migrations"
    if not migrations_dir.exists():
        log.info(f"No migrations directory found at {migrations_dir}")
        return 0

    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        return 0

    applied_count = 0
    try:
        async with pool.acquire() as conn:
            # Create migrations tracking table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )

            applied_rows = await conn.fetch("SELECT version FROM _schema_migrations")
            applied_set = {r["version"] for r in applied_rows}

            for sql_file in sql_files:
                version = sql_file.name
                if version in applied_set:
                    continue

                log.info(f"Applying pending database migration: {version}...")
                sql_content = sql_file.read_text(encoding="utf-8")

                try:
                    # Execute migration script
                    await conn.execute(sql_content)
                    await conn.execute(
                        "INSERT INTO _schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
                        version,
                    )
                    applied_count += 1
                    log.info(f"Successfully applied migration: {version}")
                except Exception as e:
                    log.error(f"Failed to apply migration {version}: {e}")
                    capture_exception(e, tags={"migration": version})
                    break

        if applied_count > 0:
            log.info(f"Database migrations complete. Applied {applied_count} new migration(s).")
        else:
            log.info("Database schema is up to date (no pending migrations).")
    except Exception as e:
        log.error(f"Error during schema migration check: {e}")
        capture_exception(e, tags={"component": "migration_runner"})

    return applied_count
