"""
ByteDaily Question History Repository — Tracks asked questions to prevent repeats.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts / scalars.
"""

from typing import Any, Dict, List, Optional
from ..client import bd_db


async def record(question_id: int, poll_id: Optional[int] = None) -> int:
    """
    Insert a history row for a posted question.
    Returns the new history row id.
    """
    return await bd_db.fetchval(
        """
        INSERT INTO bd_question_history (question_id, poll_id)
        VALUES ($1, $2)
        RETURNING id
        """,
        question_id,
        poll_id,
    )


async def get_asked_question_ids() -> List[int]:
    """Return distinct question_ids that have already been asked."""
    rows = await bd_db.fetch(
        "SELECT DISTINCT question_id FROM bd_question_history"
    )
    return [int(r["question_id"]) for r in rows]


async def count() -> int:
    """Return total history rows."""
    val = await bd_db.fetchval("SELECT COUNT(*) FROM bd_question_history")
    return int(val) if val is not None else 0


async def clear_all() -> int:
    """
    Wipe the entire history table so the question cycle can restart.
    Returns the number of deleted rows.
    """
    result = await bd_db.execute("DELETE FROM bd_question_history")
    # asyncpg returns e.g. "DELETE 12"
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0


async def get_least_recently_asked(limit: int = 1) -> List[Dict[str, Any]]:
    """
    Return active questions ordered by least-recent ask (or never asked first).
    Used as an optional LRU fallback when history is full.
    """
    return await bd_db.fetch(
        """
        SELECT q.*,
               MAX(h.asked_at) AS last_asked_at
        FROM bd_questions q
        LEFT JOIN bd_question_history h ON h.question_id = q.id
        WHERE q.is_active = TRUE
        GROUP BY q.id
        ORDER BY last_asked_at ASC NULLS FIRST
        LIMIT $1
        """,
        limit,
    )
