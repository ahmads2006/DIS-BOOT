"""
ByteDaily Question Service — Question selection logic.

Responsible for:
  - Selecting the next question to post, avoiding recent repeats
  - Filtering questions by active status
  - Returning a fully-formed question dict ready for the scheduler to embed

Does NOT touch Discord — pure data logic only.
All DB access goes through the repository layer.
"""

# TODO: Import question_repo from ..database.repositories.question_repo
# TODO: Import poll_repo from ..database.repositories.poll_repo
# TODO: Import constants (RECENT_QUESTION_LOOKBACK)
# TODO: Import random
# TODO: Import log from bridge.legacy_adapter

# TODO: async def pick_next_question() -> dict:
#   """
#   Select the next question to post.
#   Avoids repeating questions used in the last RECENT_QUESTION_LOOKBACK polls.
#   Falls back to any active question if all have been used recently.
#   Returns a dict with all bd_questions columns.
#   Raises RuntimeError if no active questions exist at all.
#   """
#   TODO: recent_ids = await poll_repo.get_recent_question_ids(limit=RECENT_QUESTION_LOOKBACK)
#   TODO: candidates = await question_repo.get_active_questions(exclude_ids=recent_ids)
#   TODO: if not candidates:
#           # All questions used recently — fallback to any active question
#           candidates = await question_repo.get_active_questions()
#   TODO: if not candidates:
#           raise RuntimeError("No active questions available in bd_questions.")
#   TODO: return random.choice(candidates)

# TODO: async def get_question_by_id(question_id: int) -> dict:
#   """Fetch a single question by its ID. Returns dict or raises if not found."""
#   TODO: row = await question_repo.get_by_id(question_id)
#   TODO: if not row:
#           raise ValueError(f"Question {question_id} not found in bd_questions.")
#   TODO: return row
