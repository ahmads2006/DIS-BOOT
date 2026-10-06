"""
Legacy Logger Adapter — Delegates to core.logging (structlog).
Ensures backward compatibility for all existing imports.
"""

from core.logging import get_logger, log, setup_structured_logging

def setup_logger(name: str = "discord_bot"):
    return get_logger(name)

__all__ = ["log", "setup_logger", "get_logger"]
