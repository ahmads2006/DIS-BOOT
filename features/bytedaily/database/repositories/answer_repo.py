"""
ByteDaily Answer Repository — Data access for bd_answers table.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.

The UNIQUE constraint on (poll_id, user_id) in the DB enforces the
"one answer per user per poll" rule at the database level.
"""

# TODO: Import bd_db from ..client

# TODO: async def insert(poll_id: int, user_id: int,
#                         chosen_answer: str, is_correct: bool) -> bool:
#   """
#   Insert a user's answer. Returns True if inserted, False if already answered
#   (duplicate silently ignored via ON CONFLICT DO NOTHING).
#   """
#   TODO: result = await bd_db.execute("""
#           INSERT INTO bd_answers (poll_id, user_id, chosen_answer, is_correct)
#           VALUES ($1, $2, $3, $4)
#           ON CONFLICT (poll_id, user_id) DO NOTHING
#           """, poll_id, user_id, chosen_answer, is_correct)
#   TODO: return result.split()[-1] == '1'  # "INSERT 0 1" means inserted, "INSERT 0 0" = skipped

# TODO: async def get_user_answer(poll_id: int, user_id: int) -> dict | None:
#   """Fetch a specific user's answer for a poll. Returns None if not answered."""
#   TODO: return await bd_db.fetchrow("""
#           SELECT * FROM bd_answers WHERE poll_id=$1 AND user_id=$2
#           """, poll_id, user_id)

# TODO: async def has_answered(poll_id: int, user_id: int) -> bool:
#   """Check if a user has already submitted an answer for this poll."""
#   TODO: val = await bd_db.fetchval("""
#           SELECT EXISTS(
#               SELECT 1 FROM bd_answers WHERE poll_id=$1 AND user_id=$2
#           )
#           """, poll_id, user_id)
#   TODO: return bool(val)

# TODO: async def get_all_for_poll(poll_id: int) -> list[dict]:
#   """Return all answers submitted for a poll (used by poll_service.close_poll)."""
#   TODO: return await bd_db.fetch(
#           "SELECT * FROM bd_answers WHERE poll_id = $1", poll_id)

# TODO: async def count_for_poll(poll_id: int) -> dict:
#   """Return aggregate counts: {total, correct, wrong}."""
#   TODO: row = await bd_db.fetchrow("""
#           SELECT
#               COUNT(*)                      AS total,
#               SUM(is_correct::int)          AS correct,
#               SUM((NOT is_correct)::int)    AS wrong
#           FROM bd_answers WHERE poll_id = $1
#           """, poll_id)
#   TODO: return dict(row) if row else {'total': 0, 'correct': 0, 'wrong': 0}
