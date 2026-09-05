<<<<<<< HEAD
# Backwards-compatibility bridge
from views.exam_views import QuestionView

__all__ = ["QuestionView"]
=======
# ======================
# ← QuestionView
# ======================
# views/question_view.py

import discord
import time
from discord.ui import View
from core.state import active_exams, cooldowns
from core.cooldowns import COOLDOWN

class QuestionView(View):
    def __init__(self, user):
        super().__init__(timeout=40)
        self.user = user

    async def interaction_check(self, interaction):
        return interaction.user == self.user

async def send_question(user, channel):
    exam = active_exams.get(user.id)
    if not exam:
        return

    q = exam["selected_questions"][exam["index"]]
    choices = "\n".join([f"{k}️⃣ {v}" for k, v in q["c"].items()])

    await channel.send(
        f"📝 السؤال {exam['index']+1}/3\n{q['q']}\n\n{choices}",
        view=QuestionView(user)
    )


        
>>>>>>> 3bb9071507dbfdff348f8abb94a36dd22d51eb70
