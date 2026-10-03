"""
ByteDaily Question Service — Question selection logic.

Responsible for:
  - Selecting the next question to post via bd_question_history (no repeats)
  - Resetting history when every active question has already been asked
  - Returning a fully-formed question dict ready for the scheduler to embed

Does NOT touch Discord — pure data logic only.
All DB access goes through the repository layer.
"""

from typing import Any, Dict
from bridge.legacy_adapter import log
from ..database.repositories import question_repo, history_repo


async def pick_next_question() -> Dict[str, Any]:
    """
    Select the next question to post.

    Strategy:
      1. Exclude every question_id present in bd_question_history.
      2. If no unused active questions remain, clear history and pick again
         (cycle restart — bot never halts for lack of questions).
      3. Raise RuntimeError only if the active question bank is empty.

    Returns a dict with all bd_questions columns.
    """
    asked_ids = await history_repo.get_asked_question_ids()
    chosen = await question_repo.get_random_question(exclude_ids=asked_ids or None)

    if chosen is None and asked_ids:
        deleted = await history_repo.clear_all()
        log.warning(
            f"ByteDaily: All active questions have been asked — "
            f"cleared {deleted} bd_question_history row(s) and restarting the cycle."
        )
        chosen = await question_repo.get_random_question()

    if chosen is None:
        # Last-resort LRU fallback (should only hit if clear somehow failed)
        lru = await history_repo.get_least_recently_asked(limit=1)
        if lru:
            chosen = lru[0]
            log.warning(
                f"ByteDaily: Falling back to least-recently-asked question #{chosen['id']}."
            )

    if chosen is None:
        raise RuntimeError("No active questions available in bd_questions.")

    log.info(
        f"ByteDaily: Picked question #{chosen['id']} "
        f"(difficulty={chosen.get('difficulty', 1)}, "
        f"history_excluded={len(asked_ids)})"
    )
    return chosen


async def record_asked(question_id: int, poll_id: int) -> None:
    """Record a successfully posted question into bd_question_history."""
    history_id = await history_repo.record(question_id=question_id, poll_id=poll_id)
    log.info(
        f"ByteDaily: Recorded question #{question_id} in history "
        f"(history_id={history_id}, poll_id={poll_id})."
    )


async def get_question_by_id(question_id: int) -> Dict[str, Any]:
    """Fetch a single question by its ID. Returns dict or raises if not found."""
    row = await question_repo.get_by_id(question_id)
    if not row:
        raise ValueError(f"Question #{question_id} not found in bd_questions.")
    return row
