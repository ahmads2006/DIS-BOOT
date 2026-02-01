# ======================
# ← ExamSelectView    
# ======================
# views/exam_select.py

import discord
from discord.ui import View
from core.exam_engine import start_exam_core

class ExamSelectView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    async def _start(self, interaction, role):
        await interaction.response.defer(ephemeral=True)
        result = await start_exam_core(interaction.user, self.guild_id, role)

        if result[0] == "ok":
            dm = result[1]
            await interaction.followup.send("📩 تم إرسال الاختبار إلى الخاص.", ephemeral=True)
            from views.question_view import send_question
            await send_question(interaction.user, dm)

        elif result[0] == "cooldown":
            await interaction.followup.send(f"⛔ انتظر {result[1]} ساعة.", ephemeral=True)

        elif result[0] == "no_questions":
            await interaction.followup.send("❌ لا توجد أسئلة.", ephemeral=True)

        elif result[0] == "dm_forbidden":
            await interaction.followup.send("❌ افتح الخاص.", ephemeral=True)

    @discord.ui.button(label="🎨 Frontend", style=discord.ButtonStyle.primary)
    async def frontend(self, i, b): await self._start(i, "frontend")

    @discord.ui.button(label="🛠 Backend", style=discord.ButtonStyle.success)
    async def backend(self, i, b): await self._start(i, "backend")
