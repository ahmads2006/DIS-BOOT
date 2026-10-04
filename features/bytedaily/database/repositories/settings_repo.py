"""
ByteDaily Settings Repository — Persistent key/value store in bd_settings.

Used for cross-host state such as:
  - leaderboard_message_id
  - current_question_message_id  (rolling window)
  - previous_result_message_id   (rolling window)
"""

from typing import Optional
from ..client import bd_db

LEADERBOARD_MESSAGE_ID_KEY = "leaderboard_message_id"
CURRENT_QUESTION_MESSAGE_ID_KEY = "current_question_message_id"
PREVIOUS_RESULT_MESSAGE_ID_KEY = "previous_result_message_id"


async def get(key: str) -> Optional[str]:
    """Return the string value for a settings key, or None if missing/null."""
    return await bd_db.fetchval(
        "SELECT value FROM bd_settings WHERE key = $1",
        key,
    )


async def set(key: str, value: Optional[str]) -> None:
    """Upsert a settings key. Pass value=None to clear."""
    await bd_db.execute(
        """
        INSERT INTO bd_settings (key, value, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            updated_at = NOW()
        """,
        key,
        value,
    )


async def get_int(key: str) -> Optional[int]:
    """Return an integer settings value, or None if missing/invalid."""
    raw = await get(key)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def set_int(key: str, value: Optional[int]) -> None:
    """Store an integer settings value (or clear with None)."""
    await set(key, str(value) if value is not None else None)


# ── Leaderboard ──────────────────────────────────────────────────────────────

async def get_leaderboard_message_id() -> Optional[int]:
    return await get_int(LEADERBOARD_MESSAGE_ID_KEY)


async def set_leaderboard_message_id(message_id: Optional[int]) -> None:
    await set_int(LEADERBOARD_MESSAGE_ID_KEY, message_id)


# ── Challenge channel rolling window ─────────────────────────────────────────

async def get_current_question_message_id() -> Optional[int]:
    return await get_int(CURRENT_QUESTION_MESSAGE_ID_KEY)


async def set_current_question_message_id(message_id: Optional[int]) -> None:
    await set_int(CURRENT_QUESTION_MESSAGE_ID_KEY, message_id)


async def get_previous_result_message_id() -> Optional[int]:
    return await get_int(PREVIOUS_RESULT_MESSAGE_ID_KEY)


async def set_previous_result_message_id(message_id: Optional[int]) -> None:
    await set_int(PREVIOUS_RESULT_MESSAGE_ID_KEY, message_id)
