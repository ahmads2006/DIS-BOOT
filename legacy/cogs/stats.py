"""
Stats Cog — Public statistics and examination metrics overview.
"""

from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

from config import ROLE_MAP
from legacy.core.database import db
from legacy.DATA import SPECIALIZATIONS


class StatsCog(commands.Cog, name="Stats"):
    """Displays global server evaluation statistics and track metrics."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="stats",
        description="عرض إحصائيات عامة عن الاختبارات ونسب النجاح / View overall technical exam statistics",
    )
    async def global_stats(self, interaction: discord.Interaction) -> None:
        """Display overall server exam metrics, pass rates, and most popular tracks."""
        await interaction.response.defer()
        stats = await db.get_stats()

        total = stats.get("total_attempts", 0)
        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)
        rate = stats.get("success_rate", 0.0)

        embed = discord.Embed(
            title="📊 إحصائيات التقييم التقني • Technical Exam Statistics",
            description=(
                "نظرة عامة وشاملة على أداء المطورين ومحاولات الاعتماد في السيرفر.\n"
                "Comprehensive overview of developer certification attempts and server pass rates.\n"
                "──────────────────────────────────"
            ),
            color=discord.Color.from_rgb(88, 101, 242),
            timestamp=datetime.now(timezone.utc),
        )

        guild_icon = interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None
        if guild_icon:
            embed.set_thumbnail(url=guild_icon)

        embed.add_field(
            name="📝 إجمالي المحاولات • Total Attempts",
            value=f"**{total:,}** محاولة • attempts",
            inline=True,
        )
        embed.add_field(
            name="✅ المحاولات الناجحة • Passed",
            value=f"**{passed:,}** ناجح • passed",
            inline=True,
        )
        embed.add_field(
            name="🎯 نسبة الاجتياز • Success Rate",
            value=f"**{rate}%**",
            inline=True,
        )

        if stats.get("popular_roles"):
            role_lines = []
            spec_map = {s["value"]: s for s in SPECIALIZATIONS}
            for rank_idx, (role_key, cnt) in enumerate(stats["popular_roles"][:5], 1):
                spec = spec_map.get(role_key)
                emoji = spec["emoji"] if spec else "📌"
                name_ar = spec["name_ar"] if spec else ROLE_MAP.get(role_key, role_key)
                name_en = spec["name_en"] if spec else role_key
                role_lines.append(f"`#{rank_idx}` {emoji} **{name_ar}** ({name_en}) — `{cnt}` محاولة • attempts")

            embed.add_field(
                name="🔥 أكثر التخصصات إقبالاً • Most Popular Tracks",
                value="\n".join(role_lines),
                inline=False,
            )

        footer_icon = self.bot.user.display_avatar.url if self.bot.user else None
        embed.set_footer(
            text="DevQuest Engine • Technical Certification Platform",
            icon_url=footer_icon,
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatsCog(bot))

