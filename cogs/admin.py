import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from core.database import db
from core.state import active_exams
from config import ROLE_MAP
import datetime

class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reset-cooldown", description="[للمشرفين] تصفير فترة الانتظار (Cooldown) لعضو محدد")
    @app_commands.describe(member="العضو المراد تصفير فترة انتظاره", role="التخصص البرمجي (اختياري - افتراضياً الكل)")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_cooldown(self, interaction: discord.Interaction, member: discord.Member, role: Optional[str] = None):
        success = await db.reset_cooldown(member.id, role)
        if success:
            role_text = f"لتخصص **{role}**" if role else "لجميع التخصصات"
            await interaction.response.send_message(
                f"✅ تم تصفير فترة الانتظار للعضو {member.mention} {role_text}.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ لا توجد فترات انتظار نشطة مسجلة للعضو {member.mention}.",
                ephemeral=True
            )

    @app_commands.command(name="exam-history", description="[للمشرفين] عرض سجل ونتائج اختبارات عضو")
    @app_commands.describe(member="العضو المراد عرض سجله")
    @app_commands.checks.has_permissions(administrator=True)
    async def exam_history(self, interaction: discord.Interaction, member: discord.Member):
        history = await db.get_user_history(member.id)
        if not history:
            await interaction.response.send_message(f"ℹ️ لا يوجد سجل اختبارات مسجل لـ {member.mention}.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📜 سجل اختبارات {member.display_name}",
            color=discord.Color.gold()
        )

        for idx, item in enumerate(history[-10:], 1):  # عرض آخر 10 محاولات
            role_name = ROLE_MAP.get(item["role"], item["role"])
            status = "✅ اجتاز" if item["passed"] else "❌ لم يجتز"
            date_str = datetime.datetime.fromtimestamp(item["timestamp"]).strftime("%Y-%m-%d %H:%M")
            embed.add_field(
                name=f"{idx}. {role_name} ({status})",
                value=f"الدرجة: `{item['score']}` | التاريخ: `{date_str}`",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="active-exams", description="[للمشرفين] عرض الاختبارات النشطة الجارية حالياً")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_active_exams(self, interaction: discord.Interaction):
        if not active_exams:
            await interaction.response.send_message("ℹ️ لا توجد اختبارات نشطة جارية حالياً.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"⚡ الاختبارات الجارية حالياً ({len(active_exams)})",
            color=discord.Color.purple()
        )

        for user_id, exam_data in active_exams.items():
            user = self.bot.get_user(user_id)
            user_name = user.name if user else f"User ID: {user_id}"
            role_name = ROLE_MAP.get(exam_data["role"], exam_data["role"])
            progress = f"{exam_data['index'] + 1}/{len(exam_data['selected_questions'])}"
            embed.add_field(
                name=f"👤 {user_name}",
                value=f"التخصص: `{role_name}` | السؤال الحالي: `{progress}`",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setup-exam-panel", description="[للمشرفين] إرسال لوحة الاختبارات الثابتة مع زر البدء الدائم في القناة")
    @app_commands.describe(channel="القناة المراد إرسال اللوحة إليها (افتراضياً القناة الحالية)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_exam_panel(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        target_channel = channel or interaction.channel
        from views.exam_views import ExamPanelLaunchView

        embed = discord.Embed(
            title="🧪 نظام الاختبارات وتحديد المسار البرمجي | Technical Exam System",
            description=(
                "مرحباً بك في مجتمع المطورين! 🚀\n"
                "هذا النظام مصمم لتقييم مهاراتك التقنية ومنحك الرتبة البرمجية المناسبة تلقائياً في السيرفر.\n\n"
                "──────────────────────────────────\n\n"
                "✨ **ما هو الاختبار التقني؟ | What is the Exam?**\n"
                "🔹 **العربية:** اختبار سريع ومباشر في التخصص البرمجي الذي تختاره لتحديد مستواك.\n"
                "🔹 **English:** A quick technical assessment in your chosen field to evaluate your skills.\n\n"
                "⏱️ **المدة الزمنية | Duration:**\n"
                "⏳ **العربية:** 60 ثانية لكل سؤال (تُرسل الأسئلة في الرسائل الخاصة DMs).\n"
                "⏳ **English:** 60 seconds per question (questions are sent directly to your DMs).\n\n"
                "🎯 **الخطوات للبدء | Steps to Start:**\n"
                "1️⃣ اضغط على زر **بدء الاختبار | Start Exam 🧪** بالأسفل.\n"
                "2️⃣ اختر تخصصك البرمجي من القائمة الخاصة التي ستظهر لك.\n"
                "3️⃣ افتح رسائلك الخاصة (DM) وأجب على الأسئلة عبر أزرار الخيارات.\n\n"
                "⚠️ **تنبيه هام | Important Notice:**\n"
                "يرجى التأكد من **فتح الرسائل الخاصة (Direct Messages)** في إعدادات خصوصية السيرفر قبل الضغط على الزر لتتمكن من استلام الأسئلة."
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )

        guild_icon = interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None
        if guild_icon:
            embed.set_thumbnail(url=guild_icon)
            embed.set_footer(text=f"{interaction.guild.name} • Technical Certification System", icon_url=guild_icon)
        else:
            embed.set_footer(text="Technical Certification System")

        view = ExamPanelLaunchView(self.bot)
        await target_channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ تم إرسال لوحة الاختبارات الثابتة بنجاح إلى القناة {target_channel.mention}!",
            ephemeral=True
        )

    @reset_cooldown.error
    @exam_history.error
    @list_active_exams.error
    @setup_exam_panel.error
    async def admin_error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ حدث خطأ أثناء تنفيذ الأمر.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
