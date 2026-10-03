"""
ByteDaily Leaderboard Service — Live persistent leaderboard embed management.

Maintains a single pinned message in BD_LEADERBOARD_CHANNEL_ID that is
updated every time a poll closes or an admin forces a refresh.

State persistence:
  The leaderboard message ID is stored in leaderboard_state.json next to
  this service's package directory so it survives bot restarts without
  requiring a new database table.

Public API:
  - refresh_leaderboard_embed(bot)  ->  full fetch + edit/create cycle
  - build_leaderboard_embed(top_users)  ->  returns a discord.Embed
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import discord

from bridge.legacy_adapter import log
from ..constants import BD_LEADERBOARD_CHANNEL_ID
from ..database.repositories import user_repo


# -- State file: persists leaderboard_message_id across restarts --------------
_STATE_FILE = Path(__file__).parent.parent / "leaderboard_state.json"


def _load_message_id() -> Optional[int]:
    """Load the saved leaderboard message ID from the state file."""
    try:
        if _STATE_FILE.exists():
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            val = data.get("message_id")
            return int(val) if val else None
    except Exception:
        pass
    return None


def _save_message_id(message_id: int) -> None:
    """Persist the leaderboard message ID to the state file."""
    try:
        _STATE_FILE.write_text(
            json.dumps({"message_id": message_id}, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning(f"ByteDaily Leaderboard: Could not save message ID to state file: {e}")


# -- Embed builder -------------------------------------------------------------

_RANK_EMOJIS: Dict[int, str] = {
    1: "🥇", 2: "🥈", 3: "🥉",
    4: "4️⃣", 5: "5️⃣", 6: "6️⃣",
    7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟",
}


def build_leaderboard_embed(top_users: List[Dict[str, Any]]) -> discord.Embed:
    """
    Build and return the leaderboard discord.Embed from a top-N users list.
    Each row must contain: user_id, rank, total_points, current_streak,
                           correct_count, wrong_count.
    """
    embed = discord.Embed(
        title="🏆 ByteDaily Leaderboard | لوحة متصدري التحدي",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )

    if not top_users:
        embed.description = (
            "لا يوجد مشاركون بعد!\n"
            "كن أول من يحل التحدي اليومي. 🚀"
        )
        embed.set_footer(text="يُحدَّث تلقائياً عند إغلاق كل تحدٍّ يومي")
        return embed

    lines: List[str] = []
    for row in top_users:
        rank = int(row.get("rank", 0))
        prefix = _RANK_EMOJIS.get(rank, f"`#{rank}`")
        user_mention = f"<@{row['user_id']}>"
        points = row.get("total_points", 0)
        streak = row.get("current_streak", 0)
        correct = int(row.get("correct_count", 0))
        wrong = int(row.get("wrong_count", 0))
        total = correct + wrong
        accuracy = f"{round(correct / total * 100)}%" if total > 0 else "—"
        lines.append(
            f"{prefix} {user_mention}\n"
            f"　　**{points}** pts　🔥 **{streak}**　✅ {accuracy}"
        )

    embed.description = "\n\n".join(lines)
    embed.set_footer(
        text="يُحدَّث تلقائياً عند إغلاق كل تحدٍّ يومي • Updated after each daily challenge closes."
    )
    return embed


# -- Main refresh function -----------------------------------------------------

async def refresh_leaderboard_embed(bot: discord.Client) -> None:
    """
    Fetch the top 10 users, build the embed, then:
      - If a saved message exists: edit it in-place.
      - Otherwise: send a new message, save its ID, and pin it.

    All errors are caught and logged — this function never raises.
    Safe to call from the scheduler or any admin command.
    """
    if not BD_LEADERBOARD_CHANNEL_ID:
        log.warning(
            "ByteDaily Leaderboard: BD_LEADERBOARD_CHANNEL_ID is not configured. "
            "Skipping leaderboard refresh."
        )
        return

    channel = bot.get_channel(BD_LEADERBOARD_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(BD_LEADERBOARD_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden) as e:
            log.warning(
                f"ByteDaily Leaderboard: Channel {BD_LEADERBOARD_CHANNEL_ID} unavailable ({e}). "
                "Ensure the bot can see that channel."
            )
            return
        except Exception as e:
            log.warning(
                f"ByteDaily Leaderboard: Failed to fetch channel {BD_LEADERBOARD_CHANNEL_ID}: {e}"
            )
            return

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        log.warning(
            f"ByteDaily Leaderboard: Channel {BD_LEADERBOARD_CHANNEL_ID} is not a text channel "
            f"(got {type(channel).__name__}). Skipping refresh."
        )
        return

    try:
        top_users = await user_repo.get_leaderboard(limit=10)
        embed = build_leaderboard_embed(top_users)

        saved_id = _load_message_id()
        if saved_id:
            try:
                msg = await channel.fetch_message(saved_id)
                await msg.edit(embed=embed)
                log.info(f"ByteDaily Leaderboard: Updated existing leaderboard message {saved_id}.")
                return
            except discord.NotFound:
                log.info(
                    "ByteDaily Leaderboard: Saved message not found "
                    "(possibly deleted manually) — creating a new one."
                )
            except Exception as e:
                log.warning(f"ByteDaily Leaderboard: Error editing saved message: {e}")

        # Create a fresh leaderboard message and pin it
        msg = await channel.send(embed=embed)
        _save_message_id(msg.id)
        try:
            await msg.pin()
            log.info(
                f"ByteDaily Leaderboard: Created and pinned new leaderboard message {msg.id} "
                f"in channel {BD_LEADERBOARD_CHANNEL_ID}."
            )
        except discord.Forbidden:
            log.warning(
                f"ByteDaily Leaderboard: Cannot pin message {msg.id} — "
                "bot lacks Manage Messages permission in leaderboard channel."
            )
        except Exception as e:
            log.warning(f"ByteDaily Leaderboard: Unexpected error pinning message {msg.id}: {e}")

    except Exception as e:
        log.error(
            f"ByteDaily Leaderboard: Unexpected error during leaderboard refresh: {e}",
            exc_info=True,
        )
