<<<<<<< HEAD
import asyncio
import os
import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID
from core.logger import log
from core.database import db
from api.server import AsyncAPIServer

intents = discord.Intents.all()

class DeveloperBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.api_server = None

    async def setup_hook(self):
        log.info("Starting bot initialization...")

        # تهيئة طبقة قاعدة البيانات
        await db.initialize()

        # تحميل الموديولات (Cogs)
        initial_extensions = [
            "cogs.onboarding",
            "cogs.exam",
            "cogs.admin",
            "cogs.stats",
        ]

        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                log.info(f"Loaded extension: {ext}")
            except Exception as e:
                log.error(f"Failed to load extension {ext}: {e}")

        # مزامنة أوامر السلاش
        try:
            if GUILD_ID:
                guild_obj = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                log.info(f"Synced {len(synced)} slash commands to Guild ID: {GUILD_ID}")
            else:
                synced = await self.tree.sync()
                log.info(f"Synced {len(synced)} global slash commands.")
        except Exception as e:
            log.error(f"Error syncing slash commands: {e}")

        # تشغيل خادم الـ API غير المتزامن
        self.api_server = AsyncAPIServer(self)
        await self.api_server.start()

    async def close(self):
        if self.api_server:
            await self.api_server.stop()
        await super().close()

bot = DeveloperBot()

@bot.event
async def on_ready():
    log.info(f"🤖 Bot is online as {bot.user} (ID: {bot.user.id})")
    log.info(f"Connected Guilds: {[g.name for g in bot.guilds]}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ ليس لديك الصلاحيات الكافية لتنفيذ هذا الأمر.")
    else:
        log.warning(f"Command error: {error}")

if __name__ == "__main__":
    if not TOKEN:
        log.critical("Missing DISCORD_TOKEN in environment or .env file!")
        raise RuntimeError("DISCORD_TOKEN is missing. Please set it in .env file.")

    bot.run(TOKEN)
=======
import discord
from discord.ext import commands
from discord.ui import View, Button
import os
import time
import random

from views.exam_select import ExamSelectView
from core.state import active_exams
from core.cooldowns import COOLDOWN
from core.exam_engine import start_exam_core   
GUILD_ID = int(os.getenv("GUILD_ID") or "1464310306892415129")  # ضع هنا معرف السيرفر الخاص بك للاختبار التجريبي

#ِِشغل API في خيط منفصل
from api.api import app
import threading

def run_api():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_api).start()

#======================
# تحميل متغيرات البيئة من ملف .env






def _load_env_file(path: str) -> None:
    """
    Minimal .env loader (KEY=VALUE per line).
    - Ignores empty lines and comments (# ...)
    - Does not override existing environment variables
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except FileNotFoundError:
        return

_load_env_file(os.path.join(os.path.dirname(__file__), ".env"))


from DATA import get_random_questions  # استيراد الأسئلة العشوائية من ملف DATA



intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


from discord import app_commands

@bot.tree.command(name="exam", description="بدء اختبار وتحديد التخصص" , guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def exam_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🧪 **اختر نوع الاختبار:**",
        view=ExamSelectView(interaction.guild.id)
    )


# ======================
# الإعدادات
# ======================

PUBLIC_LOG_CHANNEL_NAME = "exam-log"  # روم إعلان النجاح
# ----- أونبوردنغ البوت (يظهر في الرسائل الخاصة بعد قبول القوانين) -----
# صفحة القوانين في الصورة هي واجهة ديسكورد الرسمية. لا يمكن للبوت إضافة صفحة ثانية داخلها.
# البوت يرسل "اختر اللغة" كرسالة خاصة (DM) فور منح العضو إحدى الرتب أدناه.
# تأكد من: 1) تفعيل Server Members Intent في Discord Developer Portal
#          2) إضافة اسم الرتبة التي تُمنح بعد "Submit" في القائمة أدناه
RULES_ACCEPTED_ROLE_NAMES = [
    "✔ Rules Accepted",
    "Rules Accepted",
    "Member",
    "Verified",
]

# Onboarding copy (language -> key -> text)
ONBOARDING_COPY = {
    "ar": {
        "choose_lang": "اختر اللغة / Choose your language:",
        "beginner": "مبتدئ 🧑‍🎓",
        "professional": "محترف 🧑‍💻",
        "choose_level": "اختر مستواك:",
        "junior_done": "✅ تم منحك رتبة **📝 | Junior Developer**. مرحباً بك!",
        "choose_spec": "اختر تخصصك للمتابعة إلى الاختبار:",
        "exam_started": "🧪 تم إرسال الاختبار إلى هذه المحادثة. بالتوفيق! 🍀",
        "dm_closed": "❌ لا أستطيع إرسال رسائل خاصة لك. افتح الدردشة الخاصة ثم أعد قبول القوانين.",
        "cooldown_msg": "لا يمكنك إعادة الاختبار إلا بعد",
    },
    "en": {
        "choose_lang": "Choose your language:",
        "beginner": "Beginner 🧑‍🎓",
        "professional": "Professional 🧑‍💻",
        "choose_level": "Choose your level:",
        "junior_done": "✅ You have been given the **📝 | Junior Developer** role. Welcome!",
        "choose_spec": "Choose your specialization to continue to the exam:",
        "exam_started": "🧪 The exam has been sent to this chat. Good luck! 🍀",
        "dm_closed": "❌ I can't send you DMs. Please open DMs and accept the rules again.",
        "cooldown_msg": "You cannot retake this exam for another",
    },
}
ONBOARDING_INITIAL_PROMPT = "Choose your language: / اختر اللغة:"  # Shown before language choice

role_map = {
    "frontend": "🎨 | Frontend Developer",
    "backend": "⚙️| Backend Developer",
    "solutions_architect": "🏗️ | Solutions Architect",
    "system_architect": "🖥️ | System Architect",
    "security_engineer": "🛡️ |Security Engineer",
    "software_engineer": "💻 | Software Engineer",
    "fullstack_developer": "⚙️ | Full-Stack Developer",
    "mobile_developer": "📱 Mobile Developer",
    "junior_developer": "📝 | Junior Developer",
}

# ======================
# التخزين
# ======================

active_exams = {}     # الامتحانات الحالية{user_id: {"role": role, "index": question_index, "guild_id": guild_id, "selected_questions": []}}
cooldowns = {}       # {user_id: {role: timestamp}}
onboarding_sent_to = set()  # {user_id} لمنع إرسال الأونبوردنغ مرتين

# ======================
# User Onboarding Flow (Language → Level → Junior or Exam)
# ======================

class LanguageSelectView(View):
    """Step 1: Choose language. Pass guild_id so later steps can add roles / start exam."""
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def _next(self, interaction: discord.Interaction, lang: str):
        copy = ONBOARDING_COPY[lang]
        await interaction.response.edit_message(
            content=copy["choose_level"],
            view=LevelSelectView(lang=lang, guild_id=self.guild_id),
        )

    @discord.ui.button(label="Arabic 🇸🇦", style=discord.ButtonStyle.primary)
    async def arabic(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._next(interaction, "ar")

    @discord.ui.button(label="English 🇺🇸", style=discord.ButtonStyle.secondary)
    async def english(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._next(interaction, "en")


class LevelSelectView(View):
    """Step 2: Beginner (give Junior role) or Professional (show specialization → exam)."""
    def __init__(self, lang: str, guild_id: int):
        super().__init__(timeout=300)
        self.lang = lang
        self.guild_id = guild_id
        copy = ONBOARDING_COPY[lang]
        if len(self.children) >= 2:
            self.children[0].label = copy["beginner"]
            self.children[1].label = copy["professional"]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="Beginner", style=discord.ButtonStyle.primary)
    async def beginner(self, interaction: discord.Interaction, button: discord.ui.Button):
        copy = ONBOARDING_COPY[self.lang]
        await interaction.response.defer(ephemeral=False)
        guild = bot.get_guild(self.guild_id)
        if guild:
            role = discord.utils.get(guild.roles, name=role_map["junior_developer"])
            member = guild.get_member(interaction.user.id) or interaction.user
            if role and member:
                try:
                    await member.add_roles(role)
                except (discord.Forbidden, Exception) as e:
                    print(f"Onboarding add role: {e}")
        await interaction.message.edit(content=copy["junior_done"], view=None)

    @discord.ui.button(label="Professional", style=discord.ButtonStyle.secondary)
    async def professional(self, interaction: discord.Interaction, button: discord.ui.Button):
        copy = ONBOARDING_COPY[self.lang]
        await interaction.response.edit_message(
            content=copy["choose_spec"],
            view=OnboardingSpecializationView(lang=self.lang, guild_id=self.guild_id),
        )


class OnboardingSpecializationView(View):
    """Step 3 (Professional only): Same specializations as ExamSelectView; starts exam in DM."""
    def __init__(self, lang: str, guild_id: int):
        super().__init__(timeout=300)
        self.lang = lang
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def _start(self, interaction: discord.Interaction, role_key: str):
        user = interaction.user
        result = await start_exam_core(user, self.guild_id, role_key)
        copy = ONBOARDING_COPY[self.lang]
        if result[0] == "ok":
            await interaction.response.edit_message(content=copy["exam_started"], view=None)
        elif result[0] == "cooldown":
            await interaction.response.edit_message(
                content=f"⛔ {copy['cooldown_msg']} {result[1]}h.",
                view=None,
            )
        elif result[0] == "no_questions":
            await interaction.response.edit_message(
                content="❌ لا توجد أسئلة متاحة / No questions available.",
                view=None,
            )
        elif result[0] == "dm_forbidden":
            await interaction.response.edit_message(content=copy["dm_closed"], view=None)

    @discord.ui.button(label="🎨 Frontend", style=discord.ButtonStyle.primary)
    async def frontend(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "frontend")

    @discord.ui.button(label="🛠 Backend", style=discord.ButtonStyle.success)
    async def backend(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "backend")

    @discord.ui.button(label="🏗️ Solutions Architect", style=discord.ButtonStyle.danger)
    async def solutions_architect(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "solutions_architect")

    @discord.ui.button(label="🖥️ System Architect", style=discord.ButtonStyle.secondary)
    async def system_architect(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "system_architect")

    @discord.ui.button(label="🛡️ Security Engineer", style=discord.ButtonStyle.success)
    async def security_engineer(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "security_engineer")

    @discord.ui.button(label="💻 Software Engineer", style=discord.ButtonStyle.secondary, row=1)
    async def software_engineer(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "software_engineer")

    @discord.ui.button(label="⚙️ Full-Stack", style=discord.ButtonStyle.blurple, row=1)
    async def fullstack_developer(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "fullstack_developer")

    @discord.ui.button(label="📱 Mobile Developer", style=discord.ButtonStyle.success, row=1)
    async def mobile_developer(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "mobile_developer")

    @discord.ui.button(label="📝 Junior Developer", style=discord.ButtonStyle.danger, row=1)
    async def junior_developer(self, i: discord.Interaction, btn: discord.ui.Button):
        await self._start(i, "junior_developer")

# ======================
# النجاح
# ======================

async def success(user, role_key):
    exam = active_exams.get(user.id)
    if not exam:
        return

    guild = bot.get_guild(exam["guild_id"])
    if not guild:
        return

    role = discord.utils.get(guild.roles, name=role_map[role_key])

    if role:
        try:
            await user.add_roles(role)
        except discord.Forbidden:
            print("❌ لا يمكن إعطاء الرتبة")
        except Exception as e:
            print(f"Error adding role: {e}")

    log = discord.utils.get(guild.text_channels, name=PUBLIC_LOG_CHANNEL_NAME)
    if log:
        try:
            await log.send(
                f"🎉 **{user.mention}** نجح وأصبح **{role_map[role_key]}**"
            )
        except discord.Forbidden:
            print(f"Cannot send message to log channel {log.name}")
        except Exception as e:
            print(f"Error sending log message: {e}")
    else:
        print(f"Log channel '{PUBLIC_LOG_CHANNEL_NAME}' not found in guild {guild.name}")

    try:
        await user.send("🎉 مبروك! نجحت في الاختبار ✅")
    except discord.Forbidden:
        print(f"Cannot send DM to user {user.name}")
    except Exception as e:
        print(f"Error sending success DM: {e}")



# ======================
# الرسوب
# ======================

async def fail(user, role):
    cooldowns.setdefault(user.id, {})[role] = time.time() + COOLDOWN
    try:
        await user.send(
            f"❌ رسبت في اختبار **{role}**.\n"
            "⛔ لا يمكنك إعادة هذا الاختبار إلا بعد أسبوع.\n"
            "✅ يمكنك تجربة اختبار آخر."
        )
    except discord.Forbidden:
        print(f"Cannot send DM to user {user.name}")
    except Exception as e:
        print(f"Error sending failure message to user {user.name}: {e}")


# ======================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{bot.user} is ready!')
    print(f'Servers: {[guild.name for guild in bot.guilds]}')



def _member_has_rules_role(member: discord.Member) -> bool:
    """True if member has any of the rules-accepted roles."""
    names = {r.name for r in member.roles}
    return any(name in names for name in RULES_ACCEPTED_ROLE_NAMES)


async def _send_onboarding_dm(member: discord.Member) -> bool:
    """Send onboarding DM. Returns True if sent, False if skipped or failed."""
    key = (member.guild.id, member.id)
    if member.id in onboarding_sent_to:
        return False
    try:
        dm = await member.create_dm()
        await dm.send(
            ONBOARDING_INITIAL_PROMPT,
            view=LanguageSelectView(guild_id=member.guild.id),
        )
        onboarding_sent_to.add(member.id)
        print(f"Onboarding: Sent DM to {member.name} ({member.id}) after rules accepted.")
        return True
    except discord.Forbidden:
        print(f"Onboarding: Cannot DM user {member.name} (DMs closed or blocked). Ask them to allow DMs from server members.")
        return False


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """عند منح العضو إحدى رتب قبول القوانين نرسل له رسالة خاصة (صفحة البوت)."""
    before_roles = {r.name for r in before.roles}
    after_roles = {r.name for r in after.roles}
    # أي رتبة من القائمة ظهرت الآن (لم تكن عند before)
    newly_added = [name for name in RULES_ACCEPTED_ROLE_NAMES if name in after_roles and name not in before_roles]
    if not newly_added:
        return
    await _send_onboarding_dm(after)


@bot.event
async def on_member_join(member: discord.Member):
    """إذا دخل العضو وهو يملك رتبة القوانين (مثلاً بعد Submit) نرسل له الأونبوردنغ."""
    if not _member_has_rules_role(member):
        return
    await _send_onboarding_dm(member)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ ليس لديك الصلاحيات اللازمة لاستخدام هذا الأمر.")
    else:
        print(f'Command error: {error}')
        try:
            await ctx.send("❌ حدث خطأ أثناء تنفيذ الأمر.")
        except Exception:
            pass

# ======================
@bot.event
async def on_ready():
    await bot.tree.sync()


# دعم كلا الاسمين للتوافق مع Railway والأنظمة الأخرى
token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
if not token:
    raise RuntimeError(
        "Environment variable DISCORD_TOKEN or TOKEN is not set or is empty. "
        "Create a .env file next to main.py with a line like: DISCORD_TOKEN=your_discord_bot_token_here"
    )

bot.run(token)
>>>>>>> 3bb9071507dbfdff348f8abb94a36dd22d51eb70
