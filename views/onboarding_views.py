import discord
from discord.ui import View, Button
from config import ONBOARDING_COPY, ROLE_MAP
from core.logger import log
from core.exam_engine import start_exam_core, send_next_question

class LanguageSelectView(View):
    """الخطوة 1: اختيار لغة التفاعل"""
    def __init__(self, bot: discord.Client, guild_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id

    async def _choose_lang(self, interaction: discord.Interaction, lang: str):
        copy = ONBOARDING_COPY[lang]
        view = LevelSelectView(bot=self.bot, guild_id=self.guild_id, lang=lang)
        await interaction.response.edit_message(
            content=copy["choose_level"],
            view=view
        )

    @discord.ui.button(label="العربية 🇸🇦", style=discord.ButtonStyle.primary)
    async def arabic(self, i: discord.Interaction, b: Button):
        await self._choose_lang(i, "ar")

    @discord.ui.button(label="English 🇺🇸", style=discord.ButtonStyle.secondary)
    async def english(self, i: discord.Interaction, b: Button):
        await self._choose_lang(i, "en")


class LevelSelectView(View):
    """الخطوة 2: اختيار المستوى (مبتدئ يمنح Junior Role / محترف ينتقل لاختيار التخصص)"""
    def __init__(self, bot: discord.Client, guild_id: int, lang: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang
        copy = ONBOARDING_COPY[lang]

        if len(self.children) >= 2:
            self.children[0].label = copy["beginner"]
            self.children[1].label = copy["professional"]

    @discord.ui.button(label="Beginner", style=discord.ButtonStyle.primary)
    async def beginner(self, interaction: discord.Interaction, button: Button):
        copy = ONBOARDING_COPY[self.lang]
        guild = self.bot.get_guild(self.guild_id)
        if guild:
            role_name = ROLE_MAP.get("junior_developer")
            role = discord.utils.get(guild.roles, name=role_name)
            member = guild.get_member(interaction.user.id)
            if role and member:
                try:
                    await member.add_roles(role)
                    log.info(f"Granted Junior Developer role to {interaction.user.name} via Onboarding")
                except Exception as e:
                    log.error(f"Error adding junior role: {e}")

        await interaction.response.edit_message(content=copy["junior_done"], view=None)

    @discord.ui.button(label="Professional", style=discord.ButtonStyle.secondary)
    async def professional(self, interaction: discord.Interaction, button: Button):
        copy = ONBOARDING_COPY[self.lang]
        view = OnboardingSpecializationView(bot=self.bot, guild_id=self.guild_id, lang=self.lang)
        await interaction.response.edit_message(
            content=copy["choose_spec"],
            view=view
        )


class OnboardingSpecializationView(View):
    """الخطوة 3: للمحترفين - اختيار التخصص وبدء الاختبار فوراً في الخاص"""
    def __init__(self, bot: discord.Client, guild_id: int, lang: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang

    async def _start(self, interaction: discord.Interaction, role_key: str):
        await interaction.response.defer()
        copy = ONBOARDING_COPY[self.lang]
        user = interaction.user

        status, *extra = await start_exam_core(
            bot=self.bot,
            user=user,
            guild_id=self.guild_id,
            role_key=role_key,
            lang=self.lang
        )

        if status == "ok":
            dm_channel = extra[0]
            await interaction.message.edit(content=copy["exam_started"], view=None)
            await send_next_question(self.bot, user, dm_channel)
        elif status == "cooldown":
            hours = extra[0]
            await interaction.message.edit(content=f"⛔ {copy['cooldown_msg']} {hours}h.", view=None)
        elif status == "no_questions":
            await interaction.message.edit(content="❌ لا توجد أسئلة متاحة / No questions available.", view=None)
        elif status == "already_active":
            await interaction.message.edit(content=copy["active_exam_exists"], view=None)
        elif status == "dm_forbidden":
            await interaction.message.edit(content=copy["dm_closed"], view=None)

    @discord.ui.button(label="🎨 Frontend", style=discord.ButtonStyle.primary, row=0)
    async def frontend(self, i: discord.Interaction, b: Button): await self._start(i, "frontend")

    @discord.ui.button(label="⚙️ Backend", style=discord.ButtonStyle.success, row=0)
    async def backend(self, i: discord.Interaction, b: Button): await self._start(i, "backend")

    @discord.ui.button(label="🏗️ Solutions Architect", style=discord.ButtonStyle.secondary, row=0)
    async def solutions_architect(self, i: discord.Interaction, b: Button): await self._start(i, "solutions_architect")

    @discord.ui.button(label="🖥️ System Architect", style=discord.ButtonStyle.secondary, row=0)
    async def system_architect(self, i: discord.Interaction, b: Button): await self._start(i, "system_architect")

    @discord.ui.button(label="🛡️ Security Engineer", style=discord.ButtonStyle.danger, row=1)
    async def security_engineer(self, i: discord.Interaction, b: Button): await self._start(i, "security_engineer")

    @discord.ui.button(label="💻 Software Engineer", style=discord.ButtonStyle.primary, row=1)
    async def software_engineer(self, i: discord.Interaction, b: Button): await self._start(i, "software_engineer")

    @discord.ui.button(label="🌐 Full-Stack", style=discord.ButtonStyle.blurple, row=1)
    async def fullstack_developer(self, i: discord.Interaction, b: Button): await self._start(i, "fullstack_developer")

    @discord.ui.button(label="📱 Mobile Developer", style=discord.ButtonStyle.success, row=1)
    async def mobile_developer(self, i: discord.Interaction, b: Button): await self._start(i, "mobile_developer")
