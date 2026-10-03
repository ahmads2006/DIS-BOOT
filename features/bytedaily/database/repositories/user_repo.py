"""
ByteDaily User Repository — Data access for bd_users table + RPC.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.

The bd_upsert_user_stats RPC function handles the atomic upsert + streak
logic inside PostgreSQL — this repository simply calls it.
"""

from typing import Any, Dict, List, Optional
from ..client import bd_db


async def upsert_stats(
    user_id: int,
    is_correct: bool,
    points: int,
    poll_id: int,
) -> None:
    """
    Call the bd_upsert_user_stats RPC function.
    Atomically inserts or updates the user's row in bd_users,
    adjusting total_points, correct/wrong counts, and streak.
    """
    await bd_db.execute(
        """
        SELECT bd_upsert_user_stats($1, $2, $3, $4)
        """,
        user_id,
        is_correct,
        points,
        poll_id,
    )


async def get_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single user's stats row. Returns None if they've never answered."""
    return await bd_db.fetchrow(
        "SELECT * FROM bd_users WHERE user_id = $1",
        user_id,
    )


async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return the top `limit` users by total_points, with 1-based rank.
    Each dict includes: user_id, total_points, correct_count, wrong_count,
                         current_streak, best_streak, rank.
    """
    return await bd_db.fetch(
        """
        SELECT *,
            RANK() OVER (ORDER BY total_points DESC) AS rank
        FROM bd_users
        ORDER BY total_points DESC
        LIMIT $1
        """,
        limit,
    )


async def get_rank(user_id: int) -> Optional[int]:
    """
    Return the 1-based rank of a user by total_points.
    Returns None if the user is not in bd_users.
    """
    exists = await bd_db.fetchval(
        "SELECT total_points FROM bd_users WHERE user_id = $1",
        user_id,
    )
    if exists is None:
        return None

    rank = await bd_db.fetchval(
        """
        SELECT COUNT(*) + 1 FROM bd_users
        WHERE total_points > (
            SELECT total_points FROM bd_users WHERE user_id = $1
        )
        """,
        user_id,
    )
    return int(rank) if rank is not None else None
