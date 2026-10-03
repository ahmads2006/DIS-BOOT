"""
ByteDaily Question Repository — Data access for bd_questions table.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.
"""

# TODO: Import bd_db from ..client

# TODO: async def get_active_questions(exclude_ids: list[int] | None = None) -> list[dict]:
#   """
#   Return all questions where is_active=TRUE.
#   If exclude_ids is provided (non-empty), excludes those question IDs.
#   """
#   TODO: if exclude_ids:
#           query = "SELECT * FROM bd_questions WHERE is_active = TRUE AND id != ALL($1::bigint[])"
#           return await bd_db.fetch(query, exclude_ids)
#   TODO: else:
#           return await bd_db.fetch("SELECT * FROM bd_questions WHERE is_active = TRUE")

# TODO: async def get_by_id(question_id: int) -> dict | None:
#   """Fetch a single question row by ID. Returns None if not found."""
#   TODO: return await bd_db.fetchrow(
#           "SELECT * FROM bd_questions WHERE id = $1", question_id)

# TODO: async def insert(question_text: str, choice_a: str, choice_b: str,
#                         choice_c: str, choice_d: str, correct_answer: str,
#                         explanation: str = '', difficulty: int = 1,
#                         tags: list[str] | None = None) -> int:
#   """Insert a new question. Returns the new question ID."""
#   TODO: return await bd_db.fetchval("""
#           INSERT INTO bd_questions
#               (question_text, choice_a, choice_b, choice_c, choice_d,
#                correct_answer, explanation, difficulty, tags)
#           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
#           RETURNING id
#           """, question_text, choice_a, choice_b, choice_c, choice_d,
#                correct_answer, explanation, difficulty, tags or [])

# TODO: async def deactivate(question_id: int) -> bool:
#   """Set is_active=FALSE. Returns True if a row was updated."""
#   TODO: result = await bd_db.execute(
#           "UPDATE bd_questions SET is_active = FALSE WHERE id = $1", question_id)
#   TODO: return result.split()[-1] != '0'
