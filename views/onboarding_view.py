<<<<<<< HEAD
# Backwards-compatibility bridge
from views.onboarding_views import LanguageSelectView, LevelSelectView, OnboardingSpecializationView

__all__ = ["LanguageSelectView", "LevelSelectView", "OnboardingSpecializationView"]
=======
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
>>>>>>> 3bb9071507dbfdff348f8abb94a36dd22d51eb70
