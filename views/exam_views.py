import discord
from discord.ui import View, Button, Select
from core.logger import log
from core.exam_engine import start_exam_core, send_next_question, process_answer, handle_exam_timeout
from config import ONBOARDING_COPY

# ──────────────────────────────────────────────────────
#  قائمة اختيار التخصص (تظهر في DM بعد ضغط "بدء الاختبار")
# ──────────────────────────────────────────────────────

SPECIALIZATIONS = [
    {"label": "Frontend Developer",      "emoji": "🎨", "value": "frontend",             "description": "HTML, CSS, JavaScript, React, Vue..."},
    {"label": "Backend Developer",        "emoji": "⚙️", "value": "backend",              "description": "Node.js, Python, Java, APIs, Databases..."},
    {"label": "Full-Stack Developer",     "emoji": "🌐", "value": "fullstack_developer",  "description": "Frontend + Backend combined"},
    {"label": "Mobile Developer",         "emoji": "📱", "value": "mobile_developer",     "description": "Android, iOS, Flutter, React Native..."},
    {"label": "Software Engineer",        "emoji": "💻", "value": "software_engineer",    "description": "DSA, OOP, Design Patterns, Testing..."},
    {"label": "Security Engineer",        "emoji": "🛡️", "value": "security_engineer",    "description": "Cybersecurity, Penetration Testing..."},
    {"label": "Solutions Architect",      "emoji": "🏗️", "value": "solutions_architect",  "description": "Cloud Architecture, System Design..."},
    {"label": "System Architect",         "emoji": "🖥️", "value": "system_architect",     "description": "Infrastructure, Networking, DevOps..."},
]


class ExamSpecialtySelect(Select):
    """قائمة منسدلة لاختيار التخصص البرمجي"""
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
            placeholder="🔽 اختر تخصصك البرمجي | Select your specialization",
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
            # تعطيل القائمة بعد الاختيار
            self.disabled = True
            self.placeholder = f"✅ تم اختيار: {role_key}"
            await interaction.edit_original_response(view=self.view)
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
    """واجهة اختيار التخصص تحتوي على Select Menu"""
    def __init__(self, bot: discord.Client, guild_id: int, lang: str = "ar"):
        super().__init__(timeout=180)
        self.add_item(ExamSpecialtySelect(bot=bot, guild_id=guild_id, lang=lang))


# ──────────────────────────────────────────────────────
#  واجهة أزرار الأسئلة (A, B, C, D)
# ──────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────
#  زر بدء الاختبار الثابت (Persistent) في قناة test-yourself
# ──────────────────────────────────────────────────────

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
        guild_id = interaction.guild_id or 0

        # الرد الفوري في القناة (ephemeral) - تأكيد بسيط
        await interaction.response.send_message(
            "📩 تم إرسال قائمة اختيار التخصص إلى **رسائلك الخاصة (DM)**.\n"
            "⚠️ إذا لم تصلك الرسالة، تأكد من فتح الرسائل الخاصة في إعدادات السيرفر.",
            ephemeral=True
        )

        # فتح DM وإرسال قائمة التخصصات هناك
        try:
            dm = await interaction.user.create_dm()

            spec_embed = discord.Embed(
                title="🧪 نظام الاختبارات التقنية",
                description=(
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🎯 **اختر تخصصك البرمجي من القائمة أدناه لبدء الاختبار**\n\n"
                    "📋 **تعليمات الاختبار:**\n"
                    "╠ 📝 عدد الأسئلة: **3 أسئلة**\n"
                    "╠ ⏱️ الوقت لكل سؤال: **60 ثانية**\n"
                    "╠ ✅ يجب الإجابة على **جميع الأسئلة بشكل صحيح** للاجتياز\n"
                    "╚ 🔄 في حال الرسوب: فترة انتظار **أسبوع** لنفس التخصص\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "⬇️ **اختر تخصصك من القائمة:**"
                ),
                color=discord.Color.from_rgb(88, 101, 242)
            )
            spec_embed.set_footer(text="Programming & Dev • Technical Certification System")

            view = ExamSelectView(bot=bot, guild_id=guild_id)
            await dm.send(embed=spec_embed, view=view)

        except discord.Forbidden:
            # DM مقفل - إرسال إشعار إضافي
            try:
                await interaction.followup.send(
                    "❌ لا أستطيع إرسال رسائل خاصة لك!\n"
                    "📌 **الحل:** اذهب إلى إعدادات السيرفر → الخصوصية → فعّل 'الرسائل المباشرة' ثم حاول مرة أخرى.",
                    ephemeral=True
                )
            except Exception:
                pass
