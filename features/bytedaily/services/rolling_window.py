"""
ByteDaily Rolling Window — Track the two allowed challenge-channel messages by ID.

Tracked IDs (persisted in bd_settings / bd_polls):
  1. current_question_message_id  — active pinned question embed
  2. previous_result_message_id   — last poll results embed (unpinned)

Deletes are always targeted by stored message ID via get_partial_message().
Channel history scanning and purge are intentionally not used.
"""

from typing import Optional, Union

import discord

from bridge.legacy_adapter import log
from ..database.repositories import settings_repo


async def safe_delete_message(
    channel: Union[discord.TextChannel, discord.Thread],
    message_id: Optional[int],
    *,
    label: str = "message",
) -> bool:
    """
    Instantly delete a challenge-channel message by ID.
    Returns True if the delete request succeeded.
    """
    if not message_id:
        return False
    try:
        await channel.get_partial_message(int(message_id)).delete()
        log.info(f"ByteDaily RollingWindow: Deleted {label} message {message_id}.")
        return True
    except (discord.NotFound, discord.HTTPException) as e:
        # NotFound: already removed by an admin / prior cleanup
        # HTTPException: missing permissions, unknown message, rate limit, etc.
        if isinstance(e, discord.NotFound):
            log.info(
                f"ByteDaily RollingWindow: {label} message {message_id} already gone."
            )
        else:
            log.warning(
                f"ByteDaily RollingWindow: Failed deleting {label} {message_id}: {e}"
            )
        return False


async def delete_previous_result(
    channel: Union[discord.TextChannel, discord.Thread],
) -> None:
    """Step 1 — delete the oldest results embed (older than 1 cycle)."""
    prev_id = await settings_repo.get_previous_result_message_id()
    await safe_delete_message(channel, prev_id, label="previous_result")
    await settings_repo.set_previous_result_message_id(None)


async def delete_current_question(
    channel: Union[discord.TextChannel, discord.Thread],
    fallback_message_id: Optional[int] = None,
) -> None:
    """
    Remove the active question embed (used when transitioning to results).
    Prefers the settings-tracked ID; falls back to the poll's message_id.
    """
    current_id = await settings_repo.get_current_question_message_id()
    target = current_id or fallback_message_id
    await safe_delete_message(channel, target, label="current_question")
    await settings_repo.set_current_question_message_id(None)


async def save_previous_result(message_id: int) -> None:
    """Step 2 — persist the new results embed as previous_result_message_id."""
    await settings_repo.set_previous_result_message_id(message_id)


async def save_current_question(message_id: int) -> None:
    """Step 3 — persist the new active question as current_question_message_id."""
    await settings_repo.set_current_question_message_id(message_id)
