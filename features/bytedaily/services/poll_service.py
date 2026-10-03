"""
ByteDaily Poll Service — Poll lifecycle management.

Responsible for:
  - Creating a new poll record in bd_polls when a question is posted
  - Closing a poll: computing correct/wrong totals, awarding points + updating
    streaks for every participant via the bd_upsert_user_stats RPC function,
    updating poll status to 'closed'
  - Marking a poll as 'deleted' after the cleanup phase
  - Updating message IDs on the poll record (question msg, stats msg)
  - Fetching poll data for the scheduler and views

Does NOT touch Discord — pure data logic only.
All DB access goes through the repository layer.

MVP scope: No automatic role grants. Points and streak only.
"""

from typing import Any, Dict, Optional
from bridge.legacy_adapter import log
from ..constants import POINTS_CORRECT, POINTS_WRONG
from ..database.repositories import poll_repo, answer_repo, user_repo


async def create_poll(question_id: int, channel_id: int, message_id: Optional[int] = None) -> int:
    """
    Insert a new poll into bd_polls with status='open'.
    Returns the new poll_id.
    """
    return await poll_repo.create(question_id, channel_id, message_id)


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
    return await poll_repo.get_latest_by_status('open')


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
