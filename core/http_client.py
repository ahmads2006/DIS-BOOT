"""
Centralized Persistent HTTP Client Session Manager.

Reuses a single pooled aiohttp.ClientSession across the bot lifetime
to avoid socket exhaustion, eliminate redundant TLS handshakes, and reduce latency.
"""

import asyncio
from typing import Optional
import aiohttp

from core.logging import log

_SESSION: Optional[aiohttp.ClientSession] = None
_LOCK: asyncio.Lock = asyncio.Lock()


async def get_http_session() -> aiohttp.ClientSession:
    """Return the global shared ClientSession, creating it on first access."""
    global _SESSION
    if _SESSION is not None and not _SESSION.closed:
        return _SESSION

    async with _LOCK:
        if _SESSION is not None and not _SESSION.closed:
            return _SESSION

        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=20,
            ttl_dns_cache=300,
            keepalive_timeout=60,
        )
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        _SESSION = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        )
        log.info("Global aiohttp.ClientSession initialized with pooled TCP connector.")
        return _SESSION


async def close_http_session() -> None:
    """Gracefully close the global shared ClientSession during bot shutdown."""
    global _SESSION
    if _SESSION is not None and not _SESSION.closed:
        try:
            await _SESSION.close()
            # Brief sleep to allow underlying SSL transports to shut down cleanly
            await asyncio.sleep(0.05)
            log.info("Global aiohttp.ClientSession closed successfully.")
        except Exception as e:
            log.warning(f"Error closing global aiohttp session: {e}")
        finally:
            _SESSION = None
