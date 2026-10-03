"""
ByteDaily Views — Discord UI components for the daily question.

Contains two persistent views (timeout=None, survive bot restarts):

  1. ByteDailyAnswerView:
     - Four buttons: A, B, C, D  (style=primary)
     - custom_id pattern: "bd_answer_{poll_id}_{choice}"
     - On click:
         * Check if poll is still 'open' (guard against post-close clicks)
         * Check if user already answered this poll (bd_answers unique constraint)
         * If already answered → ephemeral "You've already submitted an answer."
         * If not answered → save to bd_answers, ephemeral "✅ Answer recorded."
     - After poll closes, scheduler disables buttons by editing the message

  2. ByteDailyResultView:
     - Single button: "📊 Show my result"  (style=secondary)
     - custom_id: "bd_show_result_{poll_id}"
     - On click:
         * Look up user's answer in bd_answers for this poll
         * If no answer found → ephemeral "You didn't participate in this poll."
         * If found → ephemeral embed showing:
             - Their chosen answer (e.g. "You answered: B")
             - The correct answer (e.g. "Correct answer: A")
             - ✅ Correct! or ❌ Wrong.
             - The explanation text from bd_questions

Note: Both views are registered with bot.add_view() so they work after restarts.
The poll_id is embedded in the custom_id so the correct poll can be looked up
from any interaction, even after a restart.
"""

# TODO: Import discord
# TODO: Import discord.ui (View, Button)
# TODO: Import answer_repo from .database.repositories.answer_repo
# TODO: Import poll_repo from .database.repositories.poll_repo
# TODO: Import question_repo from .database.repositories.question_repo
# TODO: Import constants (EMBED_COLOR_CORRECT, EMBED_COLOR_WRONG,
#         CUSTOM_ID_PREFIX_ANSWER, CUSTOM_ID_PREFIX_RESULT)
# TODO: Import log from bridge.legacy_adapter

# TODO: Define class ByteDailyAnswerView(discord.ui.View):
#   TODO: __init__(self, poll_id: int):
#           - super().__init__(timeout=None)
#           - self.poll_id = poll_id
#           - Dynamically add 4 buttons with correct custom_ids
#             (Note: discord.ui.button decorator can't use dynamic custom_id,
#              so buttons must be added manually via discord.ui.Button instances
#              and self.add_item())
#   TODO: async _handle_answer(self, interaction, choice: str):
#           - Defer ephemeral immediately
#           - Check poll status (poll_repo.get_by_id) — if not 'open': ephemeral already closed
#           - already = await answer_repo.has_answered(self.poll_id, interaction.user.id)
#           - if already: await interaction.followup.send("Already answered.", ephemeral=True)
#           - else:
#               * is_correct = (choice == poll's question's correct_answer) — need question lookup
#               * await answer_repo.insert(self.poll_id, user_id, choice, is_correct)
#               * await interaction.followup.send("✅ Answer recorded.", ephemeral=True)

# TODO: Define class ByteDailyResultView(discord.ui.View):
#   TODO: __init__(self, poll_id: int):
#           - super().__init__(timeout=None)
#           - self.poll_id = poll_id
#           - Add single button with custom_id = f"bd_show_result_{poll_id}"
#   TODO: async _show_result(self, interaction):
#           - Defer ephemeral
#           - answer = await answer_repo.get_user_answer(self.poll_id, interaction.user.id)
#           - if not answer: ephemeral "You didn't participate in this poll."
#           - else:
#               * poll = await poll_repo.get_by_id(self.poll_id)
#               * question = await question_repo.get_by_id(poll['question_id'])
#               * Build embed:
#                   title = "📊 Your Result"
#                   field "Your answer" = answer['chosen_answer']
#                   field "Correct answer" = question['correct_answer']
#                   field "Result" = ✅ Correct! or ❌ Wrong.
#                   field "Explanation" = question['explanation']
#                   color = EMBED_COLOR_CORRECT if is_correct else EMBED_COLOR_WRONG
#               * await interaction.followup.send(embed=embed, ephemeral=True)
