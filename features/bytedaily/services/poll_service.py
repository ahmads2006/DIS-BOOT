"""
ByteDaily Poll Service — Poll lifecycle management.

Responsible for:
  - Creating a new poll record in bd_polls when a question is posted
  - Closing a poll: computing correct/wrong totals, awarding points + updating
    streaks for every participant via the bd_upsert_user_stats RPC function,
    updating poll status to 'closed'
  - Marking a poll as 'deleted' after the cleanup phase
  - Updating message IDs on the poll record (question msg, stats msg)
  - Fetching poll data for the scheduler and views

Does NOT touch Discord — pure data logic only.
All DB access goes through the repository layer.

MVP scope: No automatic role grants. Points and streak only.
"""

# TODO: Import poll_repo from ..database.repositories.poll_repo
# TODO: Import answer_repo from ..database.repositories.answer_repo
# TODO: Import user_repo from ..database.repositories.user_repo
# TODO: Import constants (POINTS_CORRECT, POINTS_WRONG)
# TODO: Import log from bridge.legacy_adapter

# TODO: async def create_poll(question_id: int, channel_id: int, message_id: int) -> int:
#   """
#   Insert a new poll into bd_polls with status='open'.
#   Returns the new poll_id.
#   """
#   TODO: return await poll_repo.create(question_id, channel_id, message_id)

# TODO: async def close_poll(poll_id: int) -> dict:
#   """
#   Close a poll:
#     1. Fetch all answers for this poll
#     2. Compute correct_count, wrong_count, total_answers
#     3. For each answer, call user_repo.upsert_stats() with the appropriate points
#     4. Update bd_polls: status='closed', closed_at=now(), counts
#   Returns a stats dict: {total, correct, wrong, percent_correct}
#   """
#   TODO: answers = await answer_repo.get_all_for_poll(poll_id)
#   TODO: total = len(answers)
#   TODO: correct = sum(1 for a in answers if a['is_correct'])
#   TODO: wrong = total - correct
#   TODO: for answer in answers:
#           points = POINTS_CORRECT if answer['is_correct'] else POINTS_WRONG
#           await user_repo.upsert_stats(
#               user_id=answer['user_id'],
#               is_correct=answer['is_correct'],
#               points=points,
#               poll_id=poll_id
#           )
#   TODO: await poll_repo.update_status(poll_id, 'closed')
#   TODO: await poll_repo.update_counts(poll_id, total, correct, wrong)
#   TODO: percent_correct = round(correct / total * 100, 1) if total > 0 else 0
#   TODO: return {'total': total, 'correct': correct, 'wrong': wrong,
#                 'percent_correct': percent_correct}

# TODO: async def mark_deleted(poll_id: int) -> None:
#   """Mark a poll as 'deleted' after messages have been removed from Discord."""
#   TODO: await poll_repo.update_status(poll_id, 'deleted')

# TODO: async def get_open_poll() -> dict | None:
#   """Return the most recent poll with status='open', or None."""
#   TODO: return await poll_repo.get_latest_by_status('open')

# TODO: async def get_closed_poll() -> dict | None:
#   """Return the most recent poll with status='closed', or None."""
#   TODO: return await poll_repo.get_latest_by_status('closed')

# TODO: async def update_message_ids(poll_id: int, message_id: int = None,
#                                     stats_message_id: int = None) -> None:
#   """Update the message IDs stored on a poll record."""
#   TODO: await poll_repo.update_message_ids(poll_id, message_id, stats_message_id)
