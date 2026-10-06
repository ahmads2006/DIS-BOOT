"""
ByteDaily Answer Repository — Data access for bd_answers table.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.

The UNIQUE constraint on (poll_id, user_id) in the DB enforces the
"one answer per user per poll" rule at the database level.
"""

from typing import Any, Dict, List, Optional
from ..client import bd_db


async def insert(
    poll_id: int,
    user_id: int,
    chosen_answer: str,
    is_correct: bool,
) -> bool:
    """
    Insert a user's answer. Returns True if inserted, False if already answered
    (duplicate silently ignored via ON CONFLICT DO NOTHING).
    """
    result = await bd_db.execute(
        """
        INSERT INTO bd_answers (poll_id, user_id, chosen_answer, is_correct)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (poll_id, user_id) DO NOTHING
        """,
        poll_id,
        user_id,
        chosen_answer,
        is_correct,
    )
    return result.split()[-1] == '1'


async def get_user_answer(poll_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a specific user's answer for a poll. Returns None if not answered."""
    return await bd_db.fetchrow(
        """
        SELECT * FROM bd_answers WHERE poll_id = $1 AND user_id = $2
        """,
        poll_id,
        user_id,
    )


async def has_answered(poll_id: int, user_id: int) -> bool:
    """Check if a user has already submitted an answer for this poll."""
    val = await bd_db.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM bd_answers WHERE poll_id = $1 AND user_id = $2
        )
        """,
        poll_id,
        user_id,
    )
    return bool(val)


async def get_all_for_poll(poll_id: int) -> List[Dict[str, Any]]:
    """Return all answers submitted for a poll (used by poll_service.close_poll)."""
    return await bd_db.fetch(
        "SELECT * FROM bd_answers WHERE poll_id = $1",
        poll_id,
    )


async def count_for_poll(poll_id: int) -> Dict[str, int]:
    """Return aggregate counts: {total, correct, wrong}."""
    row = await bd_db.fetchrow(
        """
        SELECT
            COUNT(*)::int                                 AS total,
            COALESCE(SUM(is_correct::int), 0)::int        AS correct,
            COALESCE(SUM((NOT is_correct)::int), 0)::int  AS wrong
        FROM bd_answers WHERE poll_id = $1
        """,
        poll_id,
    )
    if row:
        return {
            'total': int(row.get('total') or 0),
            'correct': int(row.get('correct') or 0),
            'wrong': int(row.get('wrong') or 0),
        }
    return {'total': 0, 'correct': 0, 'wrong': 0}


async def get_choice_distribution(poll_id: int) -> Dict[str, Any]:
    """
    Return distribution per option (A, B, C, D) with counts and percentages.
    Used for revealing anti-bandwagon statistics ephemerally after answering.
    """
    rows = await bd_db.fetch(
        """
        SELECT chosen_answer, COUNT(*)::int AS count
        FROM bd_answers
        WHERE poll_id = $1
        GROUP BY chosen_answer
        """,
        poll_id,
    )
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    total = 0
    for r in rows:
        ans = str(r.get("chosen_answer", "")).upper()
        cnt = int(r.get("count", 0))
        if ans in counts:
            counts[ans] = cnt
        total += cnt

    percentages = {}
    for choice, count in counts.items():
        percentages[choice] = round((count / total) * 100) if total > 0 else 0

    return {
        "total": total,
        "counts": counts,
        "percentages": percentages,
    }

