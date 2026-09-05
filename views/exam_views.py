import discord
from discord.ui import View, Button, Select
from core.logger import log
from core.exam_engine import start_exam_core, send_next_question, process_answer, handle_exam_timeout
from config import ONBOARDING_COPY

# ──────────────────────────────────────────────────────
#  قائمة اختيار التخصص (تظهر في DM بعد ضغط "بدء الاختبار")
# ──────────────────────────────────────────────────────

SPECIALIZATIONS = [
    {"label": "Frontend Developer",      "emoji": "🎨", "value": "frontend",             "description": "HTML, CSS, JavaScript, React, UI/UX..."},
    {"label": "Backend Developer",        "emoji": "🔧", "value": "backend",              "description": "Python, Node.js, Databases, APIs, Servers..."},
    {"label": "Full-Stack Developer",     "emoji": "⚙️", "value": "fullstack_developer",  "description": "Frontend + Backend Combined Architecture"},
    {"label": "Mobile Developer",         "emoji": "📱", "value": "mobile_developer",     "description": "Flutter, React Native, iOS, Android..."},
    {"label": "Software Engineer",        "emoji": "💻", "value": "software_engineer",    "description": "Algorithms, Data Structures, OOP, System Core"},
    {"label": "Security Engineer",        "emoji": "🛡️", "value": "security_engineer",    "description": "Cybersecurity, PenTesting, AppSec..."},
    {"label": "Solutions Architect",      "emoji": "🏗️", "value": "solutions_architect",  "description": "Cloud Services, Scalability, High Availability"},
    {"label": "System Architect",         "emoji": "🖥️", "value": "system_architect",     "description": "DevOps, CI/CD, Networking, Linux, Infra..."},
]


class ExamSpecialtySelect(Select):
    """قائمة منسدلة أنيقة لاختيار التخصص البرمجي"""
    def __init__(self, bot: discord.Client, guild_id: int, lang: str = "ar"):
        options = [
            discord.SelectOption(
                label=spec["label"],
                emoji=spec["emoji"],
                value=spec["value"],
                description=spec["description"]
            )
            for spec in SPECIALIZATIONS
        ]
        super().__init__(
            placeholder="🔽 اختر تخصصك البرمجي لبدء الاختبار | Choose Path",
            min_values=1,
            max_values=1,
            options=options
        )
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        role_key = self.values[0]
        await interaction.response.defer()
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
            self.disabled = True
            self.placeholder = f"✅ تم تثبيت المسار: {role_key}"
            try:
                await interaction.edit_original_response(view=self.view)
            except Exception:
                pass
            await send_next_question(self.bot, interaction.user, dm_channel)
        elif status == "already_active":
            await interaction.followup.send(copy["active_exam_exists"])
        elif status == "cooldown":
            hours = extra[0]
            await interaction.followup.send(f"⛔ {copy['cooldown_msg']} {hours} ساعة.")
        elif status == "no_questions":
            await interaction.followup.send("❌ لا توجد أسئلة متاحة لهذا المسار حالياً.")
        elif status == "dm_forbidden":
            await interaction.followup.send(copy["dm_closed"])


class ExamSelectView(View):
    """واجهة اختيار التخصص تحتوي على Select Menu عصري"""
    def __init__(self, bot: discord.Client, guild_id: int, lang: str = "ar"):
        super().__init__(timeout=180)
        self.add_item(ExamSpecialtySelect(bot=bot, guild_id=guild_id, lang=lang))


# ──────────────────────────────────────────────────────
#  واجهة أزرار الأسئلة (A, B, C, D) مرتبة 2x2
# ──────────────────────────────────────────────────────

class QuestionView(View):
    """واجهة أزرار الخيارات التفاعلية لكل سؤال مرتبة شبكة 2x2"""
    def __init__(self, bot: discord.Client, user: discord.User, timeout_seconds: int = 60):
        super().__init__(timeout=timeout_seconds)
        self.bot = bot
        self.user = user
        self.answered = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def _disable_all(self, interaction: discord.Interaction, selected_choice: str = ""):
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True
                if child.label == selected_choice:
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary
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
        await self._disable_all(interaction, selected_choice=choice)
        await process_answer(self.bot, self.user, choice, interaction)

    # صف الأزرار الأول: A بجانب B
    @discord.ui.button(label="A", style=discord.ButtonStyle.primary, row=0)
    async def btn_a(self, i: discord.Interaction, b: Button): await self._answer(i, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary, row=0)
    async def btn_b(self, i: discord.Interaction, b: Button): await self._answer(i, "B")

    # صف الأزرار الثاني: C بجانب D
    @discord.ui.button(label="C", style=discord.ButtonStyle.primary, row=1)
    async def btn_c(self, i: discord.Interaction, b: Button): await self._answer(i, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary, row=1)
    async def btn_d(self, i: discord.Interaction, b: Button): await self._answer(i, "D")


# ──────────────────────────────────────────────────────
#  زر بدء الاختبار الثابت (Persistent) في قناة test-yourself
# ──────────────────────────────────────────────────────

class ExamPanelLaunchView(View):
    """واجهة الزر الثابت (Persistent) لبدء مسار الاختبار التقني"""
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
        guild_id = interaction.guild_id or 0

        # رد فوري في القناة (ephemeral)
        await interaction.response.send_message(
            "📩 تم إرسال لوحة الاختبار واختيار التخصص إلى **رسائلك الخاصة (DM)**.\n"
            "⚠️ إذا لم تصلك الرسالة، يرجى تفعيل الرسائل المباشرة في إعدادات السيرفر.",
            ephemeral=True
        )

        # فتح DM وإرسال قائمة التخصصات
        try:
            dm = await interaction.user.create_dm()

            spec_embed = discord.Embed(
                title="🧪 نظام الاختبارات التقنية وتحديد المستوى",
                description=(
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🎯 **اختر تخصصك البرمجي من القائمة المنسدلة أدناه لبدء الاختبار:**\n\n"
                    "📋 **تعليمات وقواعد الاختبار:**\n"
                    "• 📝 عدد الأسئلة: **3 أسئلة تقنية**\n"
                    "• ⏱️ الوقت المتاح: **60 ثانية لكل سؤال**\n"
                    "• 🎯 شرط الاجتياز: **الإجابة الصحيحة بنسبة 100%**\n"
                    "• 🏷️ عند النجاح: **تُمنح الرتبة تلقائياً وتُعلن في الشات العام**\n"
                    "• ⏳ في حال عدم الاجتياز: **فترة انتظار أسبوع لنفس التخصص**\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.from_rgb(88, 101, 242)
            )
            spec_embed.set_footer(text="Programming & Dev • Technical Certification System")

            view = ExamSelectView(bot=bot, guild_id=guild_id)
            await dm.send(embed=spec_embed, view=view)

        except discord.Forbidden:
            try:
                await interaction.followup.send(
                    "❌ لا يمكن للبوت إرسال رسائل في الخاص لديك!\n"
                    "📌 **يرجى فتح الرسائل الخاصة (Direct Messages) في إعدادات خصوصية السيرفر ثم المحاولة مجدداً.**",
                    ephemeral=True
                )
            except Exception:
                pass
