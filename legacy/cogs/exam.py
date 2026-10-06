"""
Exam Cog — Slash commands for technical assessments and administration.
"""

from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

from legacy.core.database import db
from legacy.core.exam_engine import handle_exam_fail
from legacy.core.logger import log
from legacy.core.state import active_exams
from legacy.views.exam_views import (
    ExamLandingLanguageView,
    build_exam_landing_embed,
    detect_user_default_language,
)


class ExamCog(commands.Cog, name="Exam"):
    """Handles starting and managing bilingual technical exams via DMs."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="exam",
        description="بدء الاختبار التقني وتحديد المستوى / Start Technical Certification Exam (DM)",
    )
    async def exam_command(self, interaction: discord.Interaction) -> None:
        """Start the technical exam flow via DM with bilingual support."""
        if interaction.user.id in active_exams:
            await interaction.response.send_message(
                "⚠️ لديك اختبار قائم بالفعل! يرجى إكمال إجابتك في الرسائل الخاصة.\n"
                "⚠️ You already have an active exam session! Please complete your pending test in DMs.",
                ephemeral=True,
            )
            return

        # Ephemeral confirmation in channel
        await interaction.response.send_message(
            "📩 تم إرسال لوحة الاختبار واختيار اللغة إلى **رسائلك الخاصة (DM)**.\n"
            "📩 The technical exam dashboard has been sent to your **Direct Messages (DMs)**.\n"
            "⚠️ إذا لم تصلك الرسالة، يرجى تفعيل الرسائل المباشرة في إعدادات السيرفر.",
            ephemeral=True,
        )

        guild_id = interaction.guild_id or 0
        try:
            dm = await interaction.user.create_dm()
            suggested = detect_user_default_language(
                interaction.user, interaction.guild
            )
            landing_embed = build_exam_landing_embed(suggested_lang=suggested)
            view = ExamLandingLanguageView(
                bot=self.bot, guild_id=guild_id, suggested_lang=suggested
            )
            await dm.send(embed=landing_embed, view=view)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ لا يمكن للبوت إرسال رسائل في الخاص لديك!\n"
                "❌ I cannot send you direct messages.\n"
                "📌 **يرجى فتح الرسائل الخاصة (Direct Messages) في إعدادات الخصوصية ثم المحاولة مجدداً.**",
                ephemeral=True,
            )

    @app_commands.command(
        name="cancel-exam",
        description="إلغاء جلسة الاختبار النشطة في الخاص / Cancel your active DM exam session",
    )
    async def cancel_exam(self, interaction: discord.Interaction) -> None:
        """Cancel the user's active exam session with penalty if in-progress."""
        user_id = interaction.user.id
        exam = active_exams.get(user_id)
        if not exam:
            await interaction.response.send_message(
                "ℹ️ ليس لديك أي اختبار نشط حالياً / You do not have an active exam in progress.",
                ephemeral=True,
            )
            return

        state = exam.get("state")
        if state == "IN_PROGRESS":
            # Strict penalty for abandoning in-progress exam
            await handle_exam_fail(self.bot, interaction.user, exam)
            await interaction.response.send_message(
                "⚠️ تم إلغاء الاختبار واحتسابه رسوباً مع تطبيق فترة انتظار لمدة أسبوع (7 أيام) في هذا التخصص.\n"
                "⚠️ Exam has been cancelled, marked as FAILED, and a 1-week cooldown has been applied for this track.",
                ephemeral=True,
            )
        else:
            # Clean cancellation before Q1
            active_exams.pop(user_id, None)
            log.info(f"User {interaction.user.name} cancelled pre-exam setup.")
            await interaction.response.send_message(
                "✅ تم إلغاء جلسة الاختبار بنجاح / Your exam session has been cancelled.",
                ephemeral=True,
            )

    @app_commands.command(
        name="reset-exam-cooldown",
        description="[أدمن] تصفير فترة انتظار الاختبار لمستخدم في حالة الظروف القاهرة / [Admin] Reset exam cooldown",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        user="المستخدم المراد تصفير فترة انتظاره / The user whose cooldown should be reset",
        track="التخصص المراد تصفيره (اختياري) / The track to reset",
    )
    @app_commands.choices(
        track=[
            app_commands.Choice(name="جميع التخصصات / All Tracks", value="all"),
            app_commands.Choice(name="🎨 Frontend Developer", value="frontend"),
            app_commands.Choice(name="🔧 Backend Developer", value="backend"),
            app_commands.Choice(name="⚙️ Full-Stack Developer", value="fullstack_developer"),
            app_commands.Choice(name="📱 Mobile Developer", value="mobile_developer"),
            app_commands.Choice(name="💻 Software Engineer", value="software_engineer"),
            app_commands.Choice(name="🏗️ Solutions Architect", value="solutions_architect"),
            app_commands.Choice(name="🖥️ System Architect", value="system_architect"),
            app_commands.Choice(name="🛡️ Security Engineer", value="security_engineer"),
            app_commands.Choice(name="📝 Junior Developer", value="junior_developer"),
        ]
    )
    async def reset_exam_cooldown(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        track: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        """Admin command: Reset exam cooldown for a user."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="غير مصرح • Permission Denied",
                    description="هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        track_val = track.value if track and track.value != "all" else None
        track_display = track.name if track else "جميع التخصصات / All Tracks"

        try:
            # Also clear any lingering active exam session for that user if stuck
            active_exams.pop(user.id, None)

            cleared = await db.reset_cooldown(user.id, track_val)
            embed = discord.Embed(
                title="✅ إعادة ضبط فترة الانتظار | Cooldown Reset",
                description=(
                    f"تمت إزالة فترة الانتظار بنجاح لـ {user.mention} (التخصص: **{track_display}**).\n"
                    f"يمكن للعضو الآن بدء الاختبار مجدداً عبر `/exam`.\n\n"
                    f"Cooldown period has been successfully reset for {user.mention} (Track: **{track_display}**).\n"
                    f"The candidate can now start a new exam via `/exam`."
                ),
                color=discord.Color.green(),
            )
            embed.set_footer(text="DevQuest Exam Administration")
            await interaction.followup.send(embed=embed, ephemeral=True)
            log.info(f"Admin {interaction.user.name} reset exam cooldown for {user.name} ({user.id}) on track={track_val}")
        except Exception as e:
            log.error(f"Error resetting cooldown for {user.name}: {e}", exc_info=True)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="خطأ • Error",
                    description=f"فشل تصفير فترة الانتظار / Failed to reset cooldown: {e}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExamCog(bot))
