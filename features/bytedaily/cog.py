"""
ByteDaily Cog — Discord extension entry point.

This Cog is loaded by main.py via bot.load_extension('features.bytedaily.cog').
It is responsible for:
  - Registering the /leaderboard slash command
  - Starting the ByteDaily scheduler loop on cog_load
  - Stopping the scheduler loop on cog_unload
  - Initializing the ByteDaily database pool on cog_load
  - Closing the ByteDaily database pool on cog_unload

The cog does NOT contain business logic — it delegates to services/.
"""

import discord
from discord import app_commands
from discord.ext import commands

from bridge.legacy_adapter import log
from features.shared.embed_helpers import make_info_embed
from .database.client import bd_db
from .scheduler import ByteDailyScheduler
from .services import stats_service


class ByteDailyCog(commands.Cog, name="ByteDaily"):
    """ByteDaily feature extension cog."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.scheduler = ByteDailyScheduler(bot)

    async def cog_load(self) -> None:
        """Initialize DB pool and start scheduler loop on extension load."""
        log.info("ByteDaily: Loading cog — initializing database pool and scheduler...")
        await bd_db.initialize()
        self.scheduler.start()
        log.info("ByteDaily: Cog load complete.")

    async def cog_unload(self) -> None:
        """Stop scheduler loop and close DB pool on extension unload."""
        log.info("ByteDaily: Unloading cog — stopping scheduler and closing database pool...")
        self.scheduler.stop()
        await bd_db.close()
        log.info("ByteDaily: Cog unload complete.")

    @app_commands.command(name="leaderboard", description="View the ByteDaily top leaderboard")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        """Slash command: Show top ByteDaily participants by points."""
        await interaction.response.defer()

        top_users = await stats_service.get_leaderboard(limit=10)

        if not top_users:
            embed = make_info_embed(
                title="🏆 ByteDaily Leaderboard",
                description="No members have participated in ByteDaily challenges yet!",
            )
            await interaction.followup.send(embed=embed)
            return

        description_lines = []
        rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}

        for row in top_users:
            rank = row.get("rank", 0)
            prefix = rank_emojis.get(rank, f"`#{rank}`")
            user_mention = f"<@{row['user_id']}>"
            points = row.get("total_points", 0)
            streak = row.get("current_streak", 0)
            description_lines.append(
                f"{prefix} {user_mention} — **{points}** pts | 🔥 Streak: **{streak}**"
            )

        embed = make_info_embed(
            title="🏆 ByteDaily Leaderboard",
            description="\n".join(description_lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Earn points and build streaks by solving daily challenges!")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Entry point for bot.load_extension('features.bytedaily.cog')."""
    await bot.add_cog(ByteDailyCog(bot))
