"""
ByteDaily Poll Repository — Data access for bd_polls table.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.
"""

from typing import Any, Dict, List, Optional
from ..client import bd_db


async def create(
    question_id: int,
    channel_id: int,
    message_id: Optional[int] = None,
) -> int:
    """Insert a new poll with status='open'. Returns new poll_id."""
    return await bd_db.fetchval(
        """
        INSERT INTO bd_polls (question_id, channel_id, message_id)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        question_id,
        channel_id,
        message_id,
    )


async def get_by_id(poll_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single poll row by ID. Returns None if not found."""
    return await bd_db.fetchrow(
        "SELECT * FROM bd_polls WHERE id = $1",
        poll_id,
    )


async def get_latest_by_status(status: str) -> Optional[Dict[str, Any]]:
    """Return the most recent poll matching the given status."""
    return await bd_db.fetchrow(
        """
        SELECT * FROM bd_polls
        WHERE status = $1
        ORDER BY opened_at DESC
        LIMIT 1
        """,
        status,
    )


async def update_status(poll_id: int, status: str) -> None:
    """Update status and set the matching timestamp (closed_at or deleted_at)."""
    if status == 'closed':
        await bd_db.execute(
            """
            UPDATE bd_polls
            SET status = $2, closed_at = now()
            WHERE id = $1
            """,
            poll_id,
            status,
        )
    elif status == 'deleted':
        await bd_db.execute(
            """
            UPDATE bd_polls
            SET status = $2, deleted_at = now()
            WHERE id = $1
            """,
            poll_id,
            status,
        )
    else:
        await bd_db.execute(
            "UPDATE bd_polls SET status = $2 WHERE id = $1",
            poll_id,
            status,
        )


async def update_message_ids(
    poll_id: int,
    message_id: Optional[int] = None,
    stats_message_id: Optional[int] = None,
) -> None:
    """Patch message_id and/or stats_message_id on a poll record."""
    if message_id is not None:
        await bd_db.execute(
            "UPDATE bd_polls SET message_id = $2 WHERE id = $1",
            poll_id,
            message_id,
        )
    if stats_message_id is not None:
        await bd_db.execute(
            "UPDATE bd_polls SET stats_message_id = $2 WHERE id = $1",
            poll_id,
            stats_message_id,
        )


async def update_counts(
    poll_id: int,
    total_answers: int,
    correct_count: int,
    wrong_count: int,
) -> None:
    """Update aggregate answer counts on a poll record."""
    await bd_db.execute(
        """
        UPDATE bd_polls
        SET total_answers = $2, correct_count = $3, wrong_count = $4
        WHERE id = $1
        """,
        poll_id,
        total_answers,
        correct_count,
        wrong_count,
    )


async def get_recent_question_ids(limit: int = 20) -> List[int]:
    """Return question_ids of the most recently opened polls (for repeat-avoidance)."""
    rows = await bd_db.fetch(
        """
        SELECT question_id FROM bd_polls
        ORDER BY opened_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [r['question_id'] for r in rows]
