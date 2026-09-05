import discord
from discord.ui import View, Button
from core.logger import log
from core.exam_engine import start_exam_core, send_next_question, process_answer, handle_exam_timeout
from config import ONBOARDING_COPY

class ExamSelectView(View):
    """واجهة اختيار التخصص للاختبار عبر أوامر السيرفر أو الرسائل الخاصة"""
    def __init__(self, bot: discord.Client, guild_id: int, lang: str = "ar"):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang

    async def _handle_selection(self, interaction: discord.Interaction, role_key: str):
        await interaction.response.defer(ephemeral=True)
        copy = ONBOARDING_COPY.get(self.lang, ONBOARDING_COPY["ar"])

        status, *extra = await start_exam_core(
            bot=self.bot,
            user=interaction.user,
            guild_id=self.guild_id,
            role_key=role_key,
            lang=self.lang
        )

        if status == "ok":
            dm_channel = extra[0]
            await interaction.followup.send(copy["exam_started"], ephemeral=True)
            await send_next_question(self.bot, interaction.user, dm_channel)
        elif status == "already_active":
            await interaction.followup.send(copy["active_exam_exists"], ephemeral=True)
        elif status == "cooldown":
            hours = extra[0]
            await interaction.followup.send(f"⛔ {copy['cooldown_msg']} {hours} ساعة.", ephemeral=True)
        elif status == "no_questions":
            await interaction.followup.send("❌ لا توجد أسئلة متاحة لهذا المسار حالياً.", ephemeral=True)
        elif status == "dm_forbidden":
            await interaction.followup.send(copy["dm_closed"], ephemeral=True)

    @discord.ui.button(label="🎨 Frontend", style=discord.ButtonStyle.primary, row=0)
    async def frontend(self, i: discord.Interaction, b: Button): await self._handle_selection(i, "frontend")

    @discord.ui.button(label="⚙️ Backend", style=discord.ButtonStyle.success, row=0)
    async def backend(self, i: discord.Interaction, b: Button): await self._handle_selection(i, "backend")

    @discord.ui.button(label="🏗️ Solutions Architect", style=discord.ButtonStyle.secondary, row=0)
    async def solutions_arch(self, i: discord.Interaction, b: Button): await self._handle_selection(i, "solutions_architect")

    @discord.ui.button(label="🖥️ System Architect", style=discord.ButtonStyle.secondary, row=0)
    async def system_arch(self, i: discord.Interaction, b: Button): await self._handle_selection(i, "system_architect")

    @discord.ui.button(label="🛡️ Security Engineer", style=discord.ButtonStyle.danger, row=1)
    async def security(self, i: discord.Interaction, b: Button): await self._handle_selection(i, "security_engineer")

    @discord.ui.button(label="💻 Software Engineer", style=discord.ButtonStyle.primary, row=1)
    async def software_eng(self, i: discord.Interaction, b: Button): await self._handle_selection(i, "software_engineer")

    @discord.ui.button(label="🌐 Full-Stack", style=discord.ButtonStyle.blurple, row=1)
    async def fullstack(self, i: discord.Interaction, b: Button): await self._handle_selection(i, "fullstack_developer")

    @discord.ui.button(label="📱 Mobile Developer", style=discord.ButtonStyle.success, row=1)
    async def mobile_dev(self, i: discord.Interaction, b: Button): await self._handle_selection(i, "mobile_developer")


class QuestionView(View):
    """واجهة أزرار الخيارات (A, B, C, D) لكل سؤال في الاختبار"""
    def __init__(self, bot: discord.Client, user: discord.User, timeout_seconds: int = 60):
        super().__init__(timeout=timeout_seconds)
        self.bot = bot
        self.user = user
        self.answered = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def _disable_all(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except Exception:
            pass

    async def on_timeout(self):
        if not self.answered:
            for child in self.children:
                child.disabled = True
            await handle_exam_timeout(self.bot, self.user)

    async def _answer(self, interaction: discord.Interaction, choice: str):
        if self.answered:
            return
        self.answered = True
        await self._disable_all(interaction)
        await process_answer(self.bot, self.user, choice, interaction)

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def btn_a(self, i: discord.Interaction, b: Button): await self._answer(i, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary)
    async def btn_b(self, i: discord.Interaction, b: Button): await self._answer(i, "B")

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary)
    async def btn_c(self, i: discord.Interaction, b: Button): await self._answer(i, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary)
    async def btn_d(self, i: discord.Interaction, b: Button): await self._answer(i, "D")


class ExamPanelLaunchView(View):
    """واجهة الزر الثابت (Persistent) الموضوعة في روم الاختبارات لبدء مسار /exam"""
    def __init__(self, bot: discord.Client = None):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="بدء الاختبار | Start Exam 🧪",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_exam_launch_btn",
        emoji="🚀"
    )
    async def launch_exam_btn(self, interaction: discord.Interaction, button: Button):
        bot = self.bot or interaction.client
        view = ExamSelectView(bot=bot, guild_id=interaction.guild_id or 0)
        embed = discord.Embed(
            title="🧪 اختر تخصصك البرمجي لبدء الاختبار",
            description=(
                "اضغط على التخصص المطلوب من الأزرار أدناه:\n"
                "• سيتم إرسال الأسئلة إليك مباشرة في **الرسائل الخاصة (DM)**.\n"
                "• تأكد من أن الرسائل الخاصة مفتوحة لديك قبل البدء.\n\n"
                "⚠️ في حال عدم الاجتياز، تُطبق فترة انتظار أسبوع لنفس التخصص."
            ),
            color=discord.Color.blue()
        )
        # إرسال الخيارات كرسالة Ephemeral خاصة بالعضو فقط حتى تظل القناة نظيفة
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

