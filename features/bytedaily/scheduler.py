"""
ByteDaily Scheduler — Manages the question lifecycle loop.

Uses discord.ext.tasks to run a periodic loop with three phases:
  Phase 1 — POST:   Select a question, post embed + answer buttons (A–D).
                     The poll is saved to bd_polls with status='open'.
  Phase 2 — CLOSE:  After 6 hours, close voting (disable buttons), award
                     points, update streaks via bd_upsert_user_stats RPC,
                     post a public stats summary message, add "Show my result"
                     button. Poll status set to 'closed'.
  Phase 3 — DELETE: After 4 more hours, delete the question message and the
                     stats message, then immediately call _post_question()
                     to start the next cycle. Poll status set to 'deleted'.

The scheduler tracks its current phase and active poll ID in memory.
On startup, it queries bd_polls to detect and resume any in-progress poll,
so a bot restart mid-cycle is handled gracefully.
"""

# TODO: Import asyncio, datetime
# TODO: Import discord
# TODO: Import discord.ext.tasks (tasks.loop or manual asyncio.create_task)
# TODO: Import question_service from .services.question_service
# TODO: Import poll_service from .services.poll_service
# TODO: Import ByteDailyAnswerView, ByteDailyResultView from .views
# TODO: Import constants (ANSWER_WINDOW_SECONDS, CLEANUP_DELAY_SECONDS, BD_CHANNEL_ID)
# TODO: Import log from bridge.legacy_adapter

# TODO: Define class ByteDailyScheduler:
#   TODO: __init__(self, bot: discord.Client)
#           - self.bot = bot
#           - self._task: asyncio.Task | None = None
#           - self._active_poll_id: int | None = None
#
#   TODO: async start(self):
#           - Check bd_polls for any poll with status='open' or 'closed'
#           - If 'open' poll found: resume by waiting remaining time then closing
#           - If 'closed' poll found: resume by waiting remaining time then deleting
#           - If no active poll: immediately call _post_question()
#           - Schedule _loop_task as asyncio.create_task
#
#   TODO: async stop(self):
#           - Cancel self._task if running
#
#   TODO: async _loop_task(self):
#           - Infinite loop:
#               1. await _post_question()           → sets poll to 'open'
#               2. await asyncio.sleep(ANSWER_WINDOW_SECONDS)
#               3. await _close_poll()              → sets poll to 'closed'
#               4. await asyncio.sleep(CLEANUP_DELAY_SECONDS)
#               5. await _delete_and_advance()      → sets poll to 'deleted'
#               6. (loop continues from step 1)
#           - Wrap in try/except to log errors without crashing
#
#   TODO: async _post_question(self):
#           - question = await question_service.pick_next_question()
#           - channel = bot.get_channel(BD_CHANNEL_ID)
#           - Build question embed (title=question text, fields=choices A-D)
#           - view = ByteDailyAnswerView(poll_id=TBD)
#           - msg = await channel.send(embed=embed, view=view)
#           - poll_id = await poll_service.create_poll(question['id'], channel.id, msg.id)
#           - self._active_poll_id = poll_id
#           - Update view with correct poll_id (re-send or edit)
#           - Register view with bot: bot.add_view(view)
#
#   TODO: async _close_poll(self):
#           - stats = await poll_service.close_poll(self._active_poll_id)
#           - channel = bot.get_channel(BD_CHANNEL_ID)
#           - Disable ByteDailyAnswerView (edit message to remove/disable buttons)
#           - Build stats embed: total answered, % correct, % wrong
#           - result_view = ByteDailyResultView(poll_id=self._active_poll_id)
#           - Edit original question message: add result_view
#           - stats_msg = await channel.send(embed=stats_embed)
#           - await poll_service.update_message_ids(poll_id, stats_message_id=stats_msg.id)
#           - Register result_view: bot.add_view(result_view)
#
#   TODO: async _delete_and_advance(self):
#           - Fetch poll from DB to get message_id, stats_message_id
#           - channel = bot.get_channel(BD_CHANNEL_ID)
#           - Try delete question message (discord.NotFound safe)
#           - Try delete stats message (discord.NotFound safe)
#           - await poll_service.mark_deleted(self._active_poll_id)
#           - self._active_poll_id = None
#           - (loop naturally proceeds to _post_question on next iteration)
