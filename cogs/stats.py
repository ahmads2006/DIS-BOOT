import discord
from discord import app_commands
from discord.ext import commands
from core.database import db
from config import ROLE_MAP

class StatsCog(commands.Cog, name="Stats"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="عرض إحصائيات عامة عن الاختبارات ونسب النجاح")
    async def global_stats(self, interaction: discord.Interaction):
        stats = await db.get_stats()

        embed = discord.Embed(
            title="📊 إحصائيات الاختبارات البرمجية",
            color=discord.Color.teal()
        )

        embed.add_field(name="إجمالي المحاولات", value=f"`{stats['total_attempts']}`", inline=True)
        embed.add_field(name="المحاولات الناجحة ✅", value=f"`{stats['passed']}`", inline=True)
        embed.add_field(name="نسبة الاجتياز 🎯", value=f"`{stats['success_rate']}%`", inline=True)

        if stats["popular_roles"]:
            top_roles_text = "\n".join(
                [f"• **{ROLE_MAP.get(r, r)}**: {cnt} محاولة" for r, cnt in stats["popular_roles"][:5]]
            )
            embed.add_field(name="🔥 أكثر التخصصات إقبالاً", value=top_roles_text, inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
