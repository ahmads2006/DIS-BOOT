"""
Sentry Integration & Observability for Discord Bot.

Features:
  - Initializes sentry-sdk with Asyncio and AioHttp integrations.
  - Automatically captures unhandled exceptions with rich contextual tags
    (user_id, guild_id, command_name, custom_id, poll_id).
  - Safe fallback if SENTRY_DSN is absent.
  - Flush handler for clean shutdown.
"""

import os
from typing import Any, Dict, Optional
import discord

from core.logging import log

try:
    import sentry_sdk
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.aiohttp import AioHttpIntegration
except ImportError:
    sentry_sdk = None
    AsyncioIntegration = None
    AioHttpIntegration = None


_SENTRY_INITIALIZED: bool = False


def init_sentry() -> bool:
    """Initialize Sentry SDK with async integrations if SENTRY_DSN is configured."""
    global _SENTRY_INITIALIZED

    if not sentry_sdk:
        log.warning("Sentry SDK is not installed — error tracking disabled.")
        return False

    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        log.info("SENTRY_DSN is not configured — running with local structured logging only.")
        return False

    env = os.getenv("ENVIRONMENT") or ("production" if os.getenv("RENDER") else "development")
    release = os.getenv("RELEASE") or os.getenv("GIT_COMMIT") or "devquest-bot@1.0.0"

    try:
        integrations = []
        if AsyncioIntegration:
            integrations.append(AsyncioIntegration())
        if AioHttpIntegration:
            integrations.append(AioHttpIntegration())

        sentry_sdk.init(
            dsn=dsn,
            environment=env,
            release=release,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
            integrations=integrations,
            send_default_pii=False,
            attach_stacktrace=True,
        )
        _SENTRY_INITIALIZED = True
        log.info("Sentry SDK initialized successfully", environment=env, release=release)
        return True
    except Exception as e:
        log.error("Failed to initialize Sentry SDK", error=str(e))
        return False


def is_sentry_active() -> bool:
    """Check if Sentry is active and capturing events."""
    return _SENTRY_INITIALIZED and sentry_sdk is not None


def capture_exception(
    exc: BaseException,
    tags: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Capture exception to Sentry with attached tags and extra context."""
    if not is_sentry_active():
        return None

    try:
        with sentry_sdk.push_scope() as scope:
            if tags:
                for k, v in tags.items():
                    if v is not None:
                        scope.set_tag(k, str(v))
            if extra:
                for k, v in extra.items():
                    scope.set_extra(k, v)
            return sentry_sdk.capture_exception(exc)
    except Exception as e:
        log.warning("Failed to forward exception to Sentry", error=str(e))
        return None


def capture_interaction_error(
    interaction: discord.Interaction,
    exc: BaseException,
    active_poll_id: Optional[int] = None,
    extra_tags: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Capture a Discord interaction or slash-command error with rich Discord context."""
    tags: Dict[str, Any] = {
        "user_id": interaction.user.id if interaction.user else "unknown",
        "user_name": str(interaction.user) if interaction.user else "unknown",
        "guild_id": interaction.guild_id or "DM",
        "channel_id": interaction.channel_id or "unknown",
    }

    if interaction.command:
        tags["command_name"] = interaction.command.name
    if interaction.data and "custom_id" in interaction.data:
        tags["interaction_custom_id"] = interaction.data["custom_id"]
    if active_poll_id is not None:
        tags["active_poll_id"] = str(active_poll_id)

    if extra_tags:
        tags.update(extra_tags)

    return capture_exception(exc, tags=tags, extra={"interaction_type": str(interaction.type)})


def flush(timeout: float = 2.0) -> None:
    """Flush any queued Sentry events before shutdown."""
    if is_sentry_active():
        try:
            sentry_sdk.flush(timeout=timeout)
            log.info("Sentry event queue flushed.")
        except Exception as e:
            log.warning("Error flushing Sentry queue", error=str(e))
