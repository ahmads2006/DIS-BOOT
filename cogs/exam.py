import discord
from discord import app_commands
from discord.ext import commands
from views.exam_views import ExamSelectView
from core.state import active_exams
from core.logger import log

class ExamCog(commands.Cog, name="Exam"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="exam", description="بدء الاختبار التقني - يتم إرسال التخصصات والأسئلة في الرسائل الخاصة")
    async def exam_command(self, interaction: discord.Interaction):
        """بدء الاختبار عبر DM"""
        # رد فوري في القناة
        await interaction.response.send_message(
            "📩 تم إرسال قائمة اختيار التخصص إلى **رسائلك الخاصة (DM)**.\n"
            "⚠️ إذا لم تصلك الرسالة، تأكد من فتح الرسائل الخاصة في إعدادات السيرفر.",
            ephemeral=True
        )

        # إرسال اختيار التخصص في DM
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

            view = ExamSelectView(bot=self.bot, guild_id=interaction.guild_id or 0)
            await dm.send(embed=spec_embed, view=view)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ لا أستطيع إرسال رسائل خاصة لك!\n"
                "📌 **الحل:** اذهب إلى إعدادات السيرفر → الخصوصية → فعّل 'الرسائل المباشرة' ثم حاول مرة أخرى.",
                ephemeral=True
            )

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
