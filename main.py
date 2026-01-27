import discord
from discord.ext import commands
from discord.ui import View, Button
import os
import time
import random

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in environment variables")


from DATA import get_random_questions  # استيراد الأسئلة العشوائية من ملف DATA



intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# الإعدادات
# ======================

PUBLIC_LOG_CHANNEL_NAME = "exam-log"  # روم إعلان النجاح

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

COOLDOWN = 7 * 24 * 60 * 60  # أسبوع

# ======================
# التخزين
# ======================

active_exams = {}     # الامتحانات الحالية{user_id: {"role": role, "index": question_index, "guild_id": guild_id, "selected_questions": []}}
cooldowns = {}       # {user_id: {role: timestamp}}

# ======================
# اختيار نوع الاختبار
# ======================

class ExamSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎨 Frontend", style=discord.ButtonStyle.primary)
    async def frontend(self, interaction, button):
        await start_exam(interaction, "frontend")

    @discord.ui.button(label="🛠 Backend", style=discord.ButtonStyle.success)
    async def backend(self, interaction, button):
        await start_exam(interaction, "backend")

    @discord.ui.button(label="🏗️ Solutions Architect", style=discord.ButtonStyle.danger)
    async def solutions_architect(self, interaction, button):
        await start_exam(interaction, "solutions_architect")

    @discord.ui.button(label="🖥️ System Architect", style=discord.ButtonStyle.secondary)
    async def system_architect(self, interaction, button):
        await start_exam(interaction, "system_architect")

    @discord.ui.button(label="🛡️ Security Engineer", style=discord.ButtonStyle.success)
    async def security_engineer(self, interaction, button):
        await start_exam(interaction, "security_engineer")

    @discord.ui.button(label="💻 Software Engineer", style=discord.ButtonStyle.secondary)
    async def software_engineer(self, interaction, button):
        await start_exam(interaction, "software_engineer")

    @discord.ui.button(label="⚙️ Full-Stack Developer", style=discord.ButtonStyle.blurple)
    async def fullstack_developer(self, interaction, button):
        await start_exam(interaction, "fullstack_developer")

    @discord.ui.button(label="📱 Mobile Developer", style=discord.ButtonStyle.success)
    async def mobile_developer(self, interaction, button):
        await start_exam(interaction, "mobile_developer")

    @discord.ui.button(label="📝 Junior Developer", style=discord.ButtonStyle.danger)
    async def junior_developer(self, interaction, button):
        await start_exam(interaction, "junior_developer")

# ======================
# بدء الاختبار
# ======================

async def start_exam(interaction, role):
    await interaction.response.defer(ephemeral=True)

    user = interaction.user
    now = time.time()

    if user.id in cooldowns and role in cooldowns[user.id]:
        remaining = max(0, int((cooldowns[user.id][role] - now) / 3600))
        try:
            await interaction.followup.send(
                f"⛔ لا يمكنك إعادة اختبار **{role}** إلا بعد {remaining} ساعة.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error sending cooldown message: {e}")
        return

    # اختيار 3 أسئلة عشوائية من ملف DATA لهذا المسار
    selected_questions = get_random_questions(role, count=3)

    # في حال لم يكن هناك أسئلة متاحة للمسار المطلوب
    if not selected_questions:
        try:
            await interaction.followup.send(
                "❌ لا توجد أسئلة متاحة لهذا الاختبار حاليًا.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error sending no-questions message: {e}")
        return
    
    active_exams[user.id] = {
        "role": role,
        "index": 0,
        "guild_id": interaction.guild.id,
        "selected_questions": selected_questions
    }

    try:
        dm = await user.create_dm()
        await dm.send("🧪 بدأ الاختبار! بالتوفيق 🍀")
        await send_question(user, dm)

        # ✅ الصحيح
        try:
            await interaction.followup.send(
                "📩 تم إرسال الاختبار إلى الخاص.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error sending followup message: {e}")

    except discord.Forbidden:
        try:
            await interaction.followup.send(
                "❌ افتح الخاص أولاً.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error sending DM error message: {e}")

# ======================
# View الأسئلة
# ======================

class QuestionView(View):
    def __init__(self, user):
        super().__init__(timeout=40)
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    async def on_timeout(self):
        # Handle timeout scenario
        if self.user.id in active_exams:
            exam = active_exams[self.user.id]
            try:
                await self.user.send("⏰ انتهى وقت الإجابة، تم إنهاء الاختبار.")
            except Exception:
                pass
            # Add cooldown for timeout
            cooldowns.setdefault(self.user.id, {})[exam["role"]] = time.time() + COOLDOWN
            del active_exams[self.user.id]

    async def answer(self, interaction, choice):
        await interaction.response.defer()

        # Check if user still has an active exam
        if self.user.id not in active_exams:
            try:
                await interaction.followup.send("❌ تم إنهاء الاختبارك مسبقًا.", ephemeral=True)
            except Exception:
                pass
            return
        
        exam = active_exams[self.user.id]
        # Use the selected questions instead of all questions
        q = exam["selected_questions"][exam["index"]]

        if choice == q["a"]:
            exam["index"] += 1

            if exam["index"] == 3:
                try:
                    await interaction.message.edit(
                        content="🎉 انتهى الاختبار!",
                        view=None
                    )
                except Exception:
                    pass
                await success(self.user, exam["role"])
                if self.user.id in active_exams:
                    del active_exams[self.user.id]
            else:
                try:
                    await interaction.message.edit(
                        content="✅ إجابة صحيحة!",
                        view=None
                    )
                except Exception:
                    pass
                await send_question(self.user, interaction.channel)
        else:
            try:
                await interaction.message.edit(
                    content="❌ إجابة خاطئة. تم إنهاء الاختبار.",
                    view=None
                )
            except Exception:
                pass
            await fail(self.user, exam["role"])
            if self.user.id in active_exams:
                del active_exams[self.user.id]

    @discord.ui.button(label="A", style=discord.ButtonStyle.blurple)
    async def a(self, interaction, button):
        await self.answer(interaction, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.blurple)
    async def b(self, interaction, button):
        await self.answer(interaction, "B")

    @discord.ui.button(label="C", style=discord.ButtonStyle.blurple)
    async def c(self, interaction, button):
        await self.answer(interaction, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.blurple)
    async def d(self, interaction, button):
        await self.answer(interaction, "D")


# ======================
# إرسال السؤال
# ======================

async def send_question(user, channel):
    # Check if user still has an active exam
    if user.id not in active_exams:
        return
        
    exam = active_exams[user.id]
    # Use the selected questions instead of all questions
    q = exam["selected_questions"][exam["index"]]
    guild = bot.get_guild(exam["guild_id"])
    choices = "\n".join([f"{k}️⃣ {v}" for k, v in q["c"].items()])

    try:
        await channel.send(
            f"📝 السؤال {exam['index']+1}/3\n"
            f"{q['q']}\n\n{choices}\n\n⏱️ 40 ثانية",
            view=QuestionView(user)
        )
    except Exception as e:
        print(f"Error sending question to user {user.name}: {e}")
        try:
            await user.send("❌ حدث خطأ أثناء إرسال السؤال.")
        except Exception:
            pass

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
# أمر إرسال الأزرار
# ======================

@bot.command()
@commands.has_permissions(administrator=True)
async def exam(ctx):
    try:
        await ctx.send(
            "🧪 **اختر نوع الاختبار:**",
            view=ExamSelectView()
        )
    except Exception as e:
        print(f"Error sending exam message: {e}")
        try:
            await ctx.send("❌ حدث خطأ أثناء إرسال رسالة الاختبار.")
        except Exception:
            pass

# ======================

@bot.event
async def on_ready():
    print(f'{bot.user} is ready!')
    print(f'Servers: {[guild.name for guild in bot.guilds]}')

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

token = os.getenv("TOKEN")
if not token:
    raise RuntimeError(
        "Environment variable TOKEN is not set or is empty. "
        "Create a .env file next to main.py with a line like: TOKEN=your_discord_bot_token_here"
    )

bot.run(token)
