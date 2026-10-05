"""
ByteDaily Leaderboard Service — Single Static Message architecture.

Maintains exactly ONE pinned leaderboard message in BD_LEADERBOARD_CHANNEL_ID.
The message ID is persisted in Supabase (`bd_settings.leaderboard_message_id`)
so every bot host edits the same message instead of posting duplicates.

Public API:
  - refresh_leaderboard_embed(bot)  ->  edit-in-place, or send + pin (no history scan)
  - build_leaderboard_embed(top_users)  ->  returns a discord.Embed
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import discord

from bridge.legacy_adapter import log
from ..constants import BD_LEADERBOARD_CHANNEL_ID, EMBED_COLOR_LEADERBOARD, EMBED_THUMBNAIL_LEADERBOARD
from ..database.repositories import settings_repo, user_repo


# Legacy local file (migrated once into bd_settings, then ignored)
_LEGACY_STATE_FILE = Path(__file__).parent.parent / "leaderboard_state.json"

_PODIUM_EMOJIS: Dict[int, str] = {1: "🥇", 2: "🥈", 3: "🥉"}
_SEPARATOR = "═══════════════════════════════"


# -- Message ID persistence (Supabase bd_settings) -----------------------------

def _load_legacy_message_id() -> Optional[int]:
    """One-time fallback: read leaderboard_state.json if it still exists."""
    try:
        if _LEGACY_STATE_FILE.exists():
            data = json.loads(_LEGACY_STATE_FILE.read_text(encoding="utf-8"))
            val = data.get("message_id")
            return int(val) if val else None
    except Exception:
        pass
    return None


async def _load_message_id() -> Optional[int]:
    """Load leaderboard_message_id from bd_settings (migrate legacy JSON if needed)."""
    saved = await settings_repo.get_leaderboard_message_id()
    if saved:
        return saved

    legacy = _load_legacy_message_id()
    if legacy:
        await settings_repo.set_leaderboard_message_id(legacy)
        log.info(
            f"ByteDaily Leaderboard: Migrated legacy message ID {legacy} "
            "from leaderboard_state.json → bd_settings."
        )
        try:
            _LEGACY_STATE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return legacy
    return None


async def _save_message_id(message_id: int) -> None:
    """Persist leaderboard_message_id to bd_settings."""
    try:
        await settings_repo.set_leaderboard_message_id(message_id)
    except Exception as e:
        log.warning(f"ByteDaily Leaderboard: Could not save message ID to bd_settings: {e}")


# -- Embed builder -------------------------------------------------------------

def build_leaderboard_embed(top_users: List[Dict[str, Any]]) -> discord.Embed:
    """
    Build and return the luxury podium-style leaderboard embed.
    Each row must contain: user_id, rank, total_points, current_streak,
                           correct_count, wrong_count.
    """
    embed = discord.Embed(
        title="🏆 LEADERBOARD | قمة متصدري DevQuest",
        color=EMBED_COLOR_LEADERBOARD,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=EMBED_THUMBNAIL_LEADERBOARD)

    if not top_users:
        embed.description = (
            "لا يوجد مشاركون بعد!\n"
            "كن أول من يحل التحدي اليومي وافتح القمة. 🚀"
        )
        embed.set_footer(
            text="🔄 التحديث تلقائي فور إغلاق كل تحدي يومي | اكتب /bytedaily-rank لمعرفة ترتيبك الشخصي"
        )
        return embed

    podium_lines: List[str] = ["**👑 THE PODIUM — القمة**", ""]
    rest_lines: List[str] = []

    for row in top_users:
        rank = int(row.get("rank", 0))
        user_mention = f"<@{row['user_id']}>"
        points = row.get("total_points", 0)
        streak = row.get("current_streak", 0)
        correct = int(row.get("correct_count", 0))
        wrong = int(row.get("wrong_count", 0))
        total = correct + wrong
        accuracy = f"{round(correct / total * 100)}%" if total > 0 else "—"

        if rank <= 3:
            medal = _PODIUM_EMOJIS.get(rank, f"`#{rank}`")
            podium_lines.append(
                f"{medal} **#{rank}** — {user_mention}\n"
                f"　　⭐ **{points}** pts　·　🔥 **{streak}** streak　·　✅ {accuracy}"
            )
        else:
            rest_lines.append(
                f"`#{rank:>2}` {user_mention}  ·  ⭐ {points} pts  ·  🔥 {streak}"
            )

    parts: List[str] = ["\n".join(podium_lines)]
    if rest_lines:
        parts.append(_SEPARATOR)
        parts.append("**📋 Contenders — المتنافسون**")
        parts.append("\n".join(rest_lines))

    embed.description = "\n".join(parts)
    embed.set_footer(
        text="🔄 التحديث تلقائي فور إغلاق كل تحدي يومي | اكتب /bytedaily-rank لمعرفة ترتيبك الشخصي"
    )
    return embed


# -- Channel helpers -----------------------------------------------------------

async def _resolve_leaderboard_channel(
    bot: discord.Client,
) -> Optional[Union[discord.TextChannel, discord.Thread]]:
    """Fetch BD_LEADERBOARD_CHANNEL_ID from cache or API."""
    if not BD_LEADERBOARD_CHANNEL_ID:
        log.warning(
            "ByteDaily Leaderboard: BD_LEADERBOARD_CHANNEL_ID is not configured. "
            "Skipping leaderboard refresh."
        )
        return None

    channel = bot.get_channel(BD_LEADERBOARD_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(BD_LEADERBOARD_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden) as e:
            log.warning(
                f"ByteDaily Leaderboard: Channel {BD_LEADERBOARD_CHANNEL_ID} unavailable ({e}). "
                "Ensure the bot can see that channel."
            )
            return None
        except Exception as e:
            log.warning(
                f"ByteDaily Leaderboard: Failed to fetch channel {BD_LEADERBOARD_CHANNEL_ID}: {e}"
            )
            return None

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        log.warning(
            f"ByteDaily Leaderboard: Channel {BD_LEADERBOARD_CHANNEL_ID} is not a text channel "
            f"(got {type(channel).__name__}). Skipping refresh."
        )
        return None

    return channel


async def _create_and_pin(
    channel: Union[discord.TextChannel, discord.Thread],
    embed: discord.Embed,
) -> Optional[discord.Message]:
    """Send a fresh embed, pin it, and save its ID (no channel history scan)."""
    msg = await channel.send(embed=embed)
    await _save_message_id(msg.id)

    try:
        await msg.pin()
        log.info(
            f"ByteDaily Leaderboard: Created and pinned static message {msg.id} "
            f"in channel {channel.id}."
        )
    except discord.Forbidden:
        log.warning(
            f"ByteDaily Leaderboard: Cannot pin message {msg.id} — "
            "bot lacks Manage Messages permission in leaderboard channel."
        )
    except Exception as e:
        log.warning(f"ByteDaily Leaderboard: Unexpected error pinning message {msg.id}: {e}")

    return msg


# -- Main refresh function -----------------------------------------------------

async def refresh_leaderboard_embed(bot: discord.Client) -> None:
    """
    Enforce the Single Static Message architecture:

      1. Resolve BD_LEADERBOARD_CHANNEL_ID.
      2. Load leaderboard_message_id from bd_settings.
      3. If found → fetch + edit in-place.
      4. If missing / deleted → send + pin a new static message, save new ID.

    Never raises — safe for scheduler and slash commands.
    """
    channel = await _resolve_leaderboard_channel(bot)
    if channel is None:
        return

    try:
        top_users = await user_repo.get_leaderboard(limit=10)
        embed = build_leaderboard_embed(top_users)

        saved_id = await _load_message_id()
        if saved_id:
            try:
                msg = await channel.fetch_message(saved_id)
                await msg.edit(embed=embed)
                log.info(
                    f"ByteDaily Leaderboard: Edited static message {saved_id} in-place."
                )
                return
            except discord.NotFound:
                log.info(
                    f"ByteDaily Leaderboard: Saved message {saved_id} not found — "
                    "creating a new static message."
                )
                await settings_repo.set_leaderboard_message_id(None)
            except Exception as e:
                log.warning(
                    f"ByteDaily Leaderboard: Error editing message {saved_id}: {e} — "
                    "recreating static message."
                )

        await _create_and_pin(channel, embed)

    except Exception as e:
        log.error(
            f"ByteDaily Leaderboard: Unexpected error during leaderboard refresh: {e}",
            exc_info=True,
        )
