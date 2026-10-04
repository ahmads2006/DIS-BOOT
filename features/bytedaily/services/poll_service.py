"""
ByteDaily Poll Service — Poll lifecycle management.

Responsible for:
  - Creating a new poll record in bd_polls when a question is posted
  - Closing a poll: computing correct/wrong totals, awarding points + updating
    streaks for every participant via the bd_upsert_user_stats RPC function,
    updating poll status to 'closed'
  - Marking a poll as 'deleted' after the cleanup phase
  - Updating message IDs on the poll record (question msg, stats msg)
  - Adjusting open-poll duration (/bytedaily-extend, /bytedaily-reduce)
  - Fetching poll data for the scheduler and views

MVP scope: No automatic role grants. Points and streak only.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import discord

from bridge.legacy_adapter import log
from ..constants import ANSWER_WINDOW_SECONDS, BD_CHANNEL_ID, POINTS_CORRECT, POINTS_WRONG
from ..database.repositories import poll_repo, answer_repo, user_repo, question_repo
from ..embeds import build_challenge_embed


class PollDurationError(ValueError):
    """Raised when a duration change would set ends_at in the past (or is otherwise invalid)."""


def resolve_ends_at(poll: Dict[str, Any]) -> datetime:
    """
    Return the absolute UTC close time for a poll.
    Prefers the stored ends_at column; falls back to opened_at + default window.
    """
    ends_at = poll.get("ends_at")
    if ends_at is not None:
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        return ends_at

    opened_at = poll.get("opened_at") or datetime.now(timezone.utc)
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)
    return opened_at + timedelta(seconds=ANSWER_WINDOW_SECONDS)


async def create_poll(
    question_id: int,
    channel_id: int,
    message_id: Optional[int] = None,
    ends_at: Optional[datetime] = None,
) -> int:
    """
    Insert a new poll into bd_polls with status='open'.
    If ends_at is omitted, defaults to now + ANSWER_WINDOW_SECONDS.
    Returns the new poll_id.
    """
    if ends_at is None:
        ends_at = datetime.now(timezone.utc) + timedelta(seconds=ANSWER_WINDOW_SECONDS)
    elif ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)

    return await poll_repo.create(
        question_id,
        channel_id,
        message_id,
        ends_at=ends_at,
    )


async def close_poll(poll_id: int) -> Dict[str, Any]:
    """
    Close a poll (Concurrency-Safe & Idempotent):
      1. Atomically attempt to transition status from 'open' to 'closed' in PostgreSQL.
      2. If transition returns False (already closed/deleted by another worker), fetch and return current stats immediately without awarding points.
      3. If transition returns True (this worker won the atomic race), process answer stats, award points/streaks, update poll counts, and return stats.
    """
    poll = await poll_repo.get_by_id(poll_id)
    if not poll:
        raise ValueError(f"Poll #{poll_id} not found in bd_polls.")

    # Attempt atomic status transition FIRST
    transitioned = await poll_repo.transition_status(poll_id, from_status='open', to_status='closed')

    answers = await answer_repo.get_all_for_poll(poll_id)
    total = len(answers)
    correct = sum(1 for a in answers if a.get('is_correct'))
    wrong = total - correct
    percent_correct = round((correct / total * 100), 1) if total > 0 else 0.0

    if not transitioned:
        # Another concurrent process or previous execution already closed/deleted this poll.
        log.info(
            f"ByteDaily: Poll #{poll_id} transition from 'open' to 'closed' skipped "
            f"(already transitioned to '{poll.get('status')}'). Returning stats without re-awarding points."
        )
        return {
            'total': total,
            'correct': correct,
            'wrong': wrong,
            'percent_correct': percent_correct,
        }

    # Only the single winner of the atomic transition awards points & updates counts
    for answer in answers:
        points = POINTS_CORRECT if answer.get('is_correct') else POINTS_WRONG
        await user_repo.upsert_stats(
            user_id=answer['user_id'],
            is_correct=bool(answer.get('is_correct')),
            points=points,
            poll_id=poll_id,
        )

    await poll_repo.update_counts(poll_id, total, correct, wrong)

    log.info(f"ByteDaily: Closed poll #{poll_id} — total={total}, correct={correct}, wrong={wrong}")

    return {
        'total': total,
        'correct': correct,
        'wrong': wrong,
        'percent_correct': percent_correct,
    }


async def mark_deleted(poll_id: int) -> None:
    """Mark a poll as 'deleted' after messages have been removed from Discord."""
    await poll_repo.update_status(poll_id, 'deleted')


async def get_open_poll() -> Optional[Dict[str, Any]]:
    """Return the most recent poll with status='open', or None."""
    return await poll_repo.get_open_poll()


async def get_closed_poll() -> Optional[Dict[str, Any]]:
    """Return the most recent poll with status='closed', or None."""
    return await poll_repo.get_latest_by_status('closed')


async def update_message_ids(
    poll_id: int,
    message_id: Optional[int] = None,
    stats_message_id: Optional[int] = None,
) -> None:
    """Update the message IDs stored on a poll record."""
    await poll_repo.update_message_ids(poll_id, message_id, stats_message_id)


async def reset_leaderboard_points() -> int:
    """
    Reset total_points and streaks for every row in bd_users.
    Returns the number of users reset.
    """
    updated = await user_repo.reset_leaderboard_points()
    log.warning(f"ByteDaily: Leaderboard points/streaks reset for {updated} user(s).")
    return updated


async def _refresh_challenge_countdown(
    bot: discord.Client,
    poll: Dict[str, Any],
    ends_at: datetime,
) -> None:
    """Rebuild and edit the active challenge embed with the new relative timestamp."""
    message_id = poll.get("message_id")
    if not message_id:
        log.warning(
            f"ByteDaily: Poll #{poll['id']} has no message_id — cannot refresh countdown embed."
        )
        return

    channel_id = poll.get("channel_id") or BD_CHANNEL_ID
    if not channel_id:
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            log.warning(f"ByteDaily: Could not fetch channel {channel_id} for countdown edit: {e}")
            return

    question = await question_repo.get_by_id(poll["question_id"])
    if not question:
        log.warning(f"ByteDaily: Question #{poll['question_id']} missing for countdown refresh.")
        return

    counts = await answer_repo.count_for_poll(poll["id"])
    footer_icon = bot.user.display_avatar.url if bot.user else None
    embed = build_challenge_embed(
        question=question,
        poll_id=poll["id"],
        closes_at=ends_at,
        participants=counts.get("total", 0),
        footer_icon_url=footer_icon,
    )

    try:
        msg = await channel.fetch_message(message_id)
        await msg.edit(embed=embed)
        log.info(
            f"ByteDaily: Updated countdown on challenge message {message_id} "
            f"→ ends_at={ends_at.isoformat()}"
        )
    except discord.NotFound:
        log.warning(f"ByteDaily: Challenge message {message_id} not found for countdown edit.")
    except Exception as e:
        log.warning(f"ByteDaily: Failed editing challenge countdown embed: {e}")


async def modify_poll_duration(
    bot: discord.Client,
    poll_id: int,
    minutes_delta: int,
) -> Dict[str, Any]:
    """
    Adjust the active poll's ends_at by minutes_delta (positive = extend, negative = reduce).

    Updates Supabase bd_polls.ends_at and refreshes the Discord challenge embed countdown.
    Raises PollDurationError if the resulting ends_at would be in the past.
    Raises ValueError if the poll is missing or not open.
    """
    poll = await poll_repo.get_by_id(poll_id)
    if not poll:
        raise ValueError(f"Poll #{poll_id} not found.")
    if poll.get("status") != "open":
        raise ValueError(f"Poll #{poll_id} is not active (status={poll.get('status')}).")

    current_ends = resolve_ends_at(poll)
    new_ends = current_ends + timedelta(minutes=minutes_delta)
    now = datetime.now(timezone.utc)

    if new_ends <= now:
        raise PollDurationError(
            "لا يمكن ضبط وقت الانتهاء في الماضي. "
            "استخدم `/bytedaily-close` لإغلاق التحدي فوراً بدلاً من تقليص الوقت أكثر من اللازم."
        )

    updated = await poll_repo.update_ends_at(poll_id, new_ends)
    if not updated:
        raise ValueError(f"Poll #{poll_id} is no longer open — duration not changed.")

    # Refresh Discord embed countdown
    poll["ends_at"] = new_ends
    await _refresh_challenge_countdown(bot, poll, new_ends)

    log.info(
        f"ByteDaily: Poll #{poll_id} ends_at adjusted by {minutes_delta:+d} min "
        f"→ {new_ends.isoformat()}"
    )
    return {
        "poll_id": poll_id,
        "ends_at": new_ends,
        "ends_at_unix": int(new_ends.timestamp()),
        "minutes_delta": minutes_delta,
    }
