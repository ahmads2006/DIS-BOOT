"""
ByteDaily Stats Service — Leaderboard and user statistics.

Responsible for:
  - Fetching the top N users by total_points for the /leaderboard command
  - Fetching a single user's stats (points, streaks, rank)
  - Returning structured dicts ready for the cog to format into embeds

Does NOT touch Discord or build embeds — pure data logic only.
All DB access goes through the repository layer.
"""

from typing import Any, Dict, List, Optional
from ..database.repositories import user_repo


async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return the top `limit` users ordered by total_points descending.
    Each dict contains: user_id, total_points, correct_count, wrong_count,
                         current_streak, best_streak, rank (1-based integer).
    Returns empty list if no users have participated yet.
    """
    return await user_repo.get_leaderboard(limit=limit)


async def get_user_stats(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Return stats for a single user including their current leaderboard rank.
    Returns None if the user has never participated in a ByteDaily poll.
    Dict contains: user_id, total_points, correct_count, wrong_count,
                   current_streak, best_streak, rank.
    """
    row = await user_repo.get_by_id(user_id)
    if not row:
        return None
    rank = await user_repo.get_rank(user_id)
    return {**row, 'rank': rank}
