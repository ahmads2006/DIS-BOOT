"""
Structured JSON Logging with structlog.

Provides:
  - Standard library logging integration with structlog.
  - JSON output in production (e.g., on Render or when LOG_FORMAT=json).
  - Human-friendly color output in local development environments.
  - Automatic injection of ISO-8601 UTC timestamp, level, logger name, and module.
  - Contextual tagging (user_id, guild_id, poll_id, etc.).
  - Performance execution duration tracker (`measure_duration`).
"""

import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional

try:
    import structlog
except ImportError:
    structlog = None


# Determine whether we should output structured JSON
def is_production() -> bool:
    return bool(
        os.getenv("RENDER")
        or os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
        or os.getenv("LOG_FORMAT", "").lower() == "json"
    )


def setup_structured_logging(root_name: str = "discord_bot") -> Any:
    """Configure structlog and standard library logging pipeline."""
    # Ensure UTF-8 console output on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    use_json = is_production()

    if use_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    if structlog:
        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    formatter = (
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
        if structlog
        else logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
    )

    # Root standard logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers on re-init
    if not root_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

        # File logging to bot.log
        try:
            log_file = Path(__file__).parent.parent / "bot.log"
            file_formatter = (
                structlog.stdlib.ProcessorFormatter(
                    foreign_pre_chain=shared_processors,
                    processors=[
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.processors.JSONRenderer() if use_json else structlog.dev.ConsoleRenderer(colors=False),
                    ],
                )
                if structlog
                else formatter
            )
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(f"Could not initialize file logger: {e}")

    # Silence overly chatty libraries
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.INFO)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)

    return get_logger(root_name)


def get_logger(name: str = "discord_bot") -> Any:
    """Return a structlog bound logger if available, otherwise a standard logger."""
    if structlog:
        return structlog.get_logger(name)
    return logging.getLogger(name)


@contextmanager
def measure_duration(event_name: str, logger: Optional[Any] = None, **tags: Any) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager to time operation execution and log duration_ms automatically.
    
    Usage:
        with measure_duration("generate_daily_question", count=5):
            await do_work()
    """
    active_log = logger or log
    start_time = time.perf_counter()
    ctx: Dict[str, Any] = {"event": event_name, **tags}
    try:
        yield ctx
    finally:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        ctx["duration_ms"] = duration_ms
        active_log.info(event_name, **ctx)


# Initialize default logger singleton
log = setup_structured_logging()
