"""
ByteDaily Stats Service — Leaderboard and user statistics.

Responsible for:
  - Fetching the top N users by total_points for the /leaderboard command
  - Fetching a single user's stats (points, streaks, rank)
  - Returning structured dicts ready for the cog to format into embeds

Does NOT touch Discord or build embeds — pure data logic only.
All DB access goes through the repository layer.
"""

# TODO: Import user_repo from ..database.repositories.user_repo
# TODO: Import log from bridge.legacy_adapter

# TODO: async def get_leaderboard(limit: int = 10) -> list[dict]:
#   """
#   Return the top `limit` users ordered by total_points descending.
#   Each dict contains: user_id, total_points, correct_count, wrong_count,
#                        current_streak, best_streak, rank (1-based integer).
#   Returns empty list if no users have participated yet.
#   """
#   TODO: return await user_repo.get_leaderboard(limit=limit)

# TODO: async def get_user_stats(user_id: int) -> dict | None:
#   """
#   Return stats for a single user including their current leaderboard rank.
#   Returns None if the user has never participated in a ByteDaily poll.
#   Dict contains: user_id, total_points, correct_count, wrong_count,
#                   current_streak, best_streak, rank.
#   """
#   TODO: row = await user_repo.get_by_id(user_id)
#   TODO: if not row:
#           return None
#   TODO: rank = await user_repo.get_rank(user_id)
#   TODO: return {**row, 'rank': rank}
