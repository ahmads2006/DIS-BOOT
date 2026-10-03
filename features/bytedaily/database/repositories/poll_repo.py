"""
ByteDaily Poll Repository — Data access for bd_polls table.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.
"""

# TODO: Import bd_db from ..client
# TODO: Import datetime (for timestamp fields)

# TODO: async def create(question_id: int, channel_id: int,
#                         message_id: int | None = None) -> int:
#   """Insert a new poll with status='open'. Returns new poll_id."""
#   TODO: return await bd_db.fetchval("""
#           INSERT INTO bd_polls (question_id, channel_id, message_id)
#           VALUES ($1, $2, $3)
#           RETURNING id
#           """, question_id, channel_id, message_id)

# TODO: async def get_by_id(poll_id: int) -> dict | None:
#   TODO: return await bd_db.fetchrow("SELECT * FROM bd_polls WHERE id = $1", poll_id)

# TODO: async def get_latest_by_status(status: str) -> dict | None:
#   """Return the most recent poll matching the given status."""
#   TODO: return await bd_db.fetchrow("""
#           SELECT * FROM bd_polls WHERE status = $1
#           ORDER BY opened_at DESC LIMIT 1
#           """, status)

# TODO: async def update_status(poll_id: int, status: str) -> None:
#   """Update status and set the matching timestamp (closed_at or deleted_at)."""
#   TODO: if status == 'closed':
#           await bd_db.execute("""
#               UPDATE bd_polls SET status=$2, closed_at=now() WHERE id=$1
#               """, poll_id, status)
#   TODO: elif status == 'deleted':
#           await bd_db.execute("""
#               UPDATE bd_polls SET status=$2, deleted_at=now() WHERE id=$1
#               """, poll_id, status)
#   TODO: else:
#           await bd_db.execute("UPDATE bd_polls SET status=$2 WHERE id=$1", poll_id, status)

# TODO: async def update_message_ids(poll_id: int, message_id: int | None = None,
#                                     stats_message_id: int | None = None) -> None:
#   """Patch message_id and/or stats_message_id on a poll record."""
#   TODO: if message_id is not None:
#           await bd_db.execute(
#               "UPDATE bd_polls SET message_id=$2 WHERE id=$1", poll_id, message_id)
#   TODO: if stats_message_id is not None:
#           await bd_db.execute(
#               "UPDATE bd_polls SET stats_message_id=$2 WHERE id=$1", poll_id, stats_message_id)

# TODO: async def update_counts(poll_id: int, total_answers: int,
#                                correct_count: int, wrong_count: int) -> None:
#   TODO: await bd_db.execute("""
#           UPDATE bd_polls
#           SET total_answers=$2, correct_count=$3, wrong_count=$4
#           WHERE id=$1
#           """, poll_id, total_answers, correct_count, wrong_count)

# TODO: async def get_recent_question_ids(limit: int = 20) -> list[int]:
#   """Return question_ids of the most recently opened polls (for repeat-avoidance)."""
#   TODO: rows = await bd_db.fetch("""
#           SELECT question_id FROM bd_polls
#           ORDER BY opened_at DESC LIMIT $1
#           """, limit)
#   TODO: return [r['question_id'] for r in rows]
