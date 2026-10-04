"""
ByteDaily Rolling Window — Enforce max 2 bot messages in the challenge channel.

Allowed messages at any time:
  1. current_question_message_id  — active pinned question embed
  2. previous_result_message_id   — last poll results embed (unpinned)

IDs are persisted in bd_settings so the window survives restarts.
"""

from typing import Optional, Set, Union

import discord

from bridge.legacy_adapter import log
from ..database.repositories import settings_repo

_HISTORY_SCAN_LIMIT = 50


async def safe_delete_message(
    channel: Union[discord.TextChannel, discord.Thread],
    message_id: Optional[int],
    *,
    label: str = "message",
) -> bool:
    """Fetch + unpin + delete a message by ID. Returns True if deleted."""
    if not message_id:
        return False
    try:
        msg = await channel.fetch_message(message_id)
    except discord.NotFound:
        log.info(f"ByteDaily RollingWindow: {label} message {message_id} already gone.")
        return False
    except Exception as e:
        log.warning(f"ByteDaily RollingWindow: Failed fetching {label} {message_id}: {e}")
        return False

    try:
        if msg.pinned:
            try:
                await msg.unpin()
            except (discord.Forbidden, discord.HTTPException):
                pass
        await msg.delete()
        log.info(f"ByteDaily RollingWindow: Deleted {label} message {message_id}.")
        return True
    except discord.NotFound:
        return False
    except discord.Forbidden:
        log.warning(
            f"ByteDaily RollingWindow: Cannot delete {label} {message_id} — missing permissions."
        )
        return False
    except Exception as e:
        log.warning(f"ByteDaily RollingWindow: Error deleting {label} {message_id}: {e}")
        return False


async def delete_previous_result(
    channel: Union[discord.TextChannel, discord.Thread],
) -> None:
    """Step 1 — purge the oldest results embed (older than 1 cycle)."""
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


async def enforce_two_message_window(
    channel: Union[discord.TextChannel, discord.Thread],
    bot_user: discord.ClientUser,
) -> int:
    """
    Delete any bot messages in the challenge channel that are NOT the
    current question or previous result. Returns number of purged messages.
    """
    keep: Set[int] = set()
    current_id = await settings_repo.get_current_question_message_id()
    previous_id = await settings_repo.get_previous_result_message_id()
    if current_id:
        keep.add(current_id)
    if previous_id:
        keep.add(previous_id)

    deleted = 0
    try:
        async for msg in channel.history(limit=_HISTORY_SCAN_LIMIT):
            if msg.author.id != bot_user.id:
                continue
            if msg.id in keep:
                continue
            try:
                if msg.pinned:
                    try:
                        await msg.unpin()
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                await msg.delete()
                deleted += 1
            except (discord.NotFound, discord.Forbidden):
                continue
            except Exception as e:
                log.warning(f"ByteDaily RollingWindow: Failed purging orphan {msg.id}: {e}")
    except discord.Forbidden:
        log.warning(
            "ByteDaily RollingWindow: Cannot scan channel history — "
            "missing Read Message History permission."
        )
    except Exception as e:
        log.warning(f"ByteDaily RollingWindow: enforce_two_message_window failed: {e}")

    if deleted:
        log.info(
            f"ByteDaily RollingWindow: Purged {deleted} orphan bot message(s); "
            f"keeping {sorted(keep) or 'none'}."
        )
    return deleted
