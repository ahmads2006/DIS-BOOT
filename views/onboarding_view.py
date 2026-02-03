# ======================
# ← All Onboarding Views
# ======================
import discord
from discord.ui import View
from core.exam_engine import start_exam

class OnboardingView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎨 Frontend", style=discord.ButtonStyle.primary)
    async def frontend(self, interaction, button):
        await start_exam(interaction, "frontend")