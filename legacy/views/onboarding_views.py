"""
Onboarding Views — Bilingual onboarding flow for new server members.
"""

from typing import Optional
import discord
from discord.ui import Button, View

from config import EXAM_BILINGUAL_COPY, ROLE_MAP
from legacy.core.exam_engine import send_next_question, start_exam_core
from legacy.core.logger import log
from legacy.views.exam_views import ExamSelectView, build_track_select_embed


class LanguageSelectView(View):
    """Step 1: Onboarding Language Selection."""

    def __init__(self, bot: discord.Client, guild_id: int) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id

    async def _choose_lang(self, interaction: discord.Interaction, lang: str) -> None:
        copy = EXAM_BILINGUAL_COPY.get(lang, EXAM_BILINGUAL_COPY["ar"])
        view = LevelSelectView(bot=self.bot, guild_id=self.guild_id, lang=lang)
        embed = discord.Embed(
            title="🎯 " + ("تحديد المستوى" if lang == "ar" else "Select Experience Level"),
            description=copy["choose_level"],
            color=discord.Color.from_rgb(88, 101, 242),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    @discord.ui.button(label="🇸🇦 العربية", style=discord.ButtonStyle.primary)
    async def arabic(self, i: discord.Interaction, b: Button) -> None:
        await self._choose_lang(i, "ar")

    @discord.ui.button(label="🇬🇧 English", style=discord.ButtonStyle.secondary)
    async def english(self, i: discord.Interaction, b: Button) -> None:
        await self._choose_lang(i, "en")


class LevelSelectView(View):
    """Step 2: Choose level (Beginner gets Junior role / Professional proceeds to exam)."""

    def __init__(self, bot: discord.Client, guild_id: int, lang: str = "ar") -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang
        copy = EXAM_BILINGUAL_COPY.get(lang, EXAM_BILINGUAL_COPY["ar"])

        if len(self.children) >= 2:
            self.children[0].label = copy["beginner"]
            self.children[1].label = copy["professional"]

    @discord.ui.button(label="Beginner", style=discord.ButtonStyle.primary)
    async def beginner(self, interaction: discord.Interaction, button: Button) -> None:
        copy = EXAM_BILINGUAL_COPY.get(self.lang, EXAM_BILINGUAL_COPY["ar"])
        guild = self.bot.get_guild(self.guild_id)
        if guild:
            role_name = ROLE_MAP.get("junior_developer")
            role = discord.utils.get(guild.roles, name=role_name)
            member = guild.get_member(interaction.user.id)
            if not member:
                try:
                    member = await guild.fetch_member(interaction.user.id)
                except Exception:
                    member = None
            if role and member:
                try:
                    await member.add_roles(role, reason="Onboarding: Selected Junior Developer")
                    log.info(f"Granted Junior Developer role to {interaction.user.name}")
                except Exception as e:
                    log.error(f"Error adding junior role: {e}")

        embed = discord.Embed(
            title="🎉 " + ("مرحباً بك!" if self.lang == "ar" else "Welcome!"),
            description=copy["junior_done"],
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    @discord.ui.button(label="Professional", style=discord.ButtonStyle.secondary)
    async def professional(self, interaction: discord.Interaction, button: Button) -> None:
        embed = build_track_select_embed(lang=self.lang)
        view = ExamSelectView(bot=self.bot, guild_id=self.guild_id, lang=self.lang)
        await interaction.response.edit_message(content=None, embed=embed, view=view)
