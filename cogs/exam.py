import discord
from discord import app_commands
from discord.ext import commands
from views.exam_views import ExamSelectView
from core.state import active_exams
from core.logger import log

class ExamCog(commands.Cog, name="Exam"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="exam", description="إرسال لوحة اختيار مسار الاختبار التقني")
    async def exam_command(self, interaction: discord.Interaction):
        """إرسال لوحة اختيار التخصصات"""
        view = ExamSelectView(bot=self.bot, guild_id=interaction.guild_id or 0)
        embed = discord.Embed(
            title="🧪 الاختبارات البرمجية لتحديد المستوى والتخصص",
            description=(
                "اختر التخصص الذي ترغب في اختباره بالضغط على أحد الأزرار أدناه.\n"
                "سيتم إرسال الأسئلة إليك في **الرسائل الخاصة (DM)**.\n\n"
                "⚠️ **تنبيه:** في حال الرسوب، تُطبق فترة انتظار أسبوع قبل إمكانية إعادة نفس المسار."
            ),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="cancel-exam", description="إلغاء جلسة الاختبار النشطة الخاصة بك في الرسائل الخاصة")
    async def cancel_exam(self, interaction: discord.Interaction):
        """إلغاء الاختبار النشط"""
        if interaction.user.id in active_exams:
            active_exams.pop(interaction.user.id, None)
            log.info(f"User {interaction.user.name} cancelled their active exam.")
            await interaction.response.send_message("✅ تم إلغاء جلستك النشطة بنجاح.", ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ ليس لديك أي اختبار نشط حالياً.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ExamCog(bot))
