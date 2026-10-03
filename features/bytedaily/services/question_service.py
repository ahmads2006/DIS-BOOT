"""
ByteDaily Question Service — Question selection logic.

Responsible for:
  - Selecting the next question to post, avoiding recent repeats
  - Filtering questions by active status
  - Returning a fully-formed question dict ready for the scheduler to embed

Does NOT touch Discord — pure data logic only.
All DB access goes through the repository layer.
"""

import random
from typing import Any, Dict
from bridge.legacy_adapter import log
from ..constants import RECENT_QUESTION_LOOKBACK
from ..database.repositories import question_repo, poll_repo


async def pick_next_question() -> Dict[str, Any]:
    """
    Select the next question to post.
    Avoids repeating questions used in the last RECENT_QUESTION_LOOKBACK polls.
    Falls back to any active question if all have been used recently.
    Returns a dict with all bd_questions columns.
    Raises RuntimeError if no active questions exist at all.
    """
    recent_ids = await poll_repo.get_recent_question_ids(limit=RECENT_QUESTION_LOOKBACK)
    candidates = await question_repo.get_active_questions(exclude_ids=recent_ids)

    if not candidates:
        # Fallback to any active question if lookback excluded all
        candidates = await question_repo.get_active_questions()

    if not candidates:
        raise RuntimeError("No active questions available in bd_questions.")

    chosen = random.choice(candidates)
    log.info(f"ByteDaily: Picked question #{chosen['id']} (difficulty={chosen.get('difficulty', 1)})")
    return chosen


async def get_question_by_id(question_id: int) -> Dict[str, Any]:
    """Fetch a single question by its ID. Returns dict or raises if not found."""
    row = await question_repo.get_by_id(question_id)
    if not row:
        raise ValueError(f"Question #{question_id} not found in bd_questions.")
    return row
