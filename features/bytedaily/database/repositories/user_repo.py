"""
ByteDaily User Repository — Data access for bd_users table + RPC.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.

The bd_upsert_user_stats RPC function handles the atomic upsert + streak
logic inside PostgreSQL — this repository simply calls it.
"""

# TODO: Import bd_db from ..client

# TODO: async def upsert_stats(user_id: int, is_correct: bool,
#                               points: int, poll_id: int) -> None:
#   """
#   Call the bd_upsert_user_stats RPC function.
#   Atomically inserts or updates the user's row in bd_users,
#   adjusting total_points, correct/wrong counts, and streak.
#   """
#   TODO: await bd_db.execute("""
#           SELECT bd_upsert_user_stats($1, $2, $3, $4)
#           """, user_id, is_correct, points, poll_id)

# TODO: async def get_by_id(user_id: int) -> dict | None:
#   """Fetch a single user's stats row. Returns None if they've never answered."""
#   TODO: return await bd_db.fetchrow(
#           "SELECT * FROM bd_users WHERE user_id = $1", user_id)

# TODO: async def get_leaderboard(limit: int = 10) -> list[dict]:
#   """
#   Return the top `limit` users by total_points, with 1-based rank.
#   Each dict includes: user_id, total_points, correct_count, wrong_count,
#                        current_streak, best_streak, rank.
#   """
#   TODO: return await bd_db.fetch("""
#           SELECT *,
#               RANK() OVER (ORDER BY total_points DESC) AS rank
#           FROM bd_users
#           ORDER BY total_points DESC
#           LIMIT $1
#           """, limit)

# TODO: async def get_rank(user_id: int) -> int | None:
#   """
#   Return the 1-based rank of a user by total_points.
#   Returns None if the user is not in bd_users.
#   """
#   TODO: exists = await bd_db.fetchval(
#           "SELECT total_points FROM bd_users WHERE user_id = $1", user_id)
#   TODO: if exists is None:
#           return None
#   TODO: rank = await bd_db.fetchval("""
#           SELECT COUNT(*) + 1 FROM bd_users
#           WHERE total_points > (
#               SELECT total_points FROM bd_users WHERE user_id = $1
#           )
#           """, user_id)
#   TODO: return int(rank)
