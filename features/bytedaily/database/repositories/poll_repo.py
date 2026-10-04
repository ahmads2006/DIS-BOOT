"""
ByteDaily Poll Repository — Data access for bd_polls table.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from ..client import bd_db


async def create(
    question_id: int,
    channel_id: int,
    message_id: Optional[int] = None,
    ends_at: Optional[datetime] = None,
) -> int:
    """Insert a new poll with status='open'. Returns new poll_id."""
    if ends_at is not None:
        return await bd_db.fetchval(
            """
            INSERT INTO bd_polls (question_id, channel_id, message_id, ends_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            question_id,
            channel_id,
            message_id,
            ends_at,
        )
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


async def get_open_poll() -> Optional[Dict[str, Any]]:
    """Return the most recent open (active) poll, or None."""
    return await get_latest_by_status("open")


async def update_ends_at(poll_id: int, ends_at: datetime) -> bool:
    """
    Set ends_at on an open poll. Returns True if a row was updated.
    Only updates polls that are still status='open'.
    """
    result = await bd_db.execute(
        """
        UPDATE bd_polls
        SET ends_at = $2
        WHERE id = $1 AND status = 'open'
        """,
        poll_id,
        ends_at,
    )
    return result.split()[-1] == "1"


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


async def transition_status(poll_id: int, from_status: str, to_status: str) -> bool:
    """
    Atomically transition poll status from `from_status` to `to_status`.
    Returns True if this execution successfully changed the status,
    or False if another execution already changed it.
    """
    if to_status == 'closed':
        result = await bd_db.execute(
            """
            UPDATE bd_polls
            SET status = $2, closed_at = now()
            WHERE id = $1 AND status = $3
            """,
            poll_id,
            to_status,
            from_status,
        )
    elif to_status == 'deleted':
        result = await bd_db.execute(
            """
            UPDATE bd_polls
            SET status = $2, deleted_at = now()
            WHERE id = $1 AND status = $3
            """,
            poll_id,
            to_status,
            from_status,
        )
    else:
        result = await bd_db.execute(
            "UPDATE bd_polls SET status = $2 WHERE id = $1 AND status = $3",
            poll_id,
            to_status,
            from_status,
        )
    return result.split()[-1] == '1'


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
