"""
ByteDaily Cog — Discord extension entry point.

This Cog is loaded by main.py via bot.load_extension('features.bytedaily.cog').
It is responsible for:
  - Registering public and admin slash commands (/leaderboard, /bytedaily-post, /bytedaily-close, /bytedaily-add-question, /bytedaily-status, /bytedaily-generate-ai)
  - Starting the ByteDaily scheduler loop on cog_load
  - Stopping the scheduler loop on cog_unload
  - Initializing the ByteDaily database pool on cog_load
  - Closing the ByteDaily database pool on cog_unload

The cog delegates business logic to services/ and database repositories.
"""

from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

from bridge.legacy_adapter import log
from features.shared.embed_helpers import (
    make_info_embed,
    make_error_embed,
    make_success_embed,
)
from .constants import BD_CHANNEL_ID
from .database.client import bd_db
from .database.repositories import question_repo
from .scheduler import ByteDailyScheduler
from .services import poll_service, question_service, stats_service, ai_generator_service


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

    # ─────────────────────────────────────────────────────────────────────────
    # Public Slash Commands
    # ─────────────────────────────────────────────────────────────────────────

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

    # ─────────────────────────────────────────────────────────────────────────
    # Admin Slash Commands
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="bytedaily-post",
        description="[Admin] Manually post a new ByteDaily challenge immediately",
    )
    @app_commands.default_permissions(administrator=True)
    async def bytedaily_post(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Admin command: Post a new question immediately."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed("Permission Denied", "Only administrators can run this command."),
                ephemeral=True,
            )
            return

        open_poll = await poll_service.get_open_poll()
        if open_poll:
            await interaction.followup.send(
                embed=make_error_embed(
                    "Poll Already Open",
                    f"There is already an active poll (**#{open_poll['id']}**). Close it first before posting a new one.",
                ),
                ephemeral=True,
            )
            return

        # Resolve target channel: parameter > default BD_CHANNEL_ID
        target_channel = channel or (self.bot.get_channel(BD_CHANNEL_ID) if BD_CHANNEL_ID else None)
        if not target_channel:
            await interaction.followup.send(
                embed=make_error_embed(
                    "Target Channel Not Found",
                    "Target channel not found. Please set BD_CHANNEL_ID or specify a channel parameter.",
                ),
                ephemeral=True,
            )
            return

        try:
            await self.scheduler._post_question(target_channel=target_channel)
            open_poll = await poll_service.get_open_poll()
            poll_id_str = f"#{open_poll['id']}" if open_poll else "new"
            await interaction.followup.send(
                embed=make_success_embed(
                    "Challenge Posted",
                    f"Successfully posted a new ByteDaily challenge ({poll_id_str}) to {target_channel.mention}!",
                ),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: Error posting challenge manually: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Posting Error", f"Failed to post challenge: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-close",
        description="[Admin] Manually close the currently active ByteDaily poll",
    )
    @app_commands.default_permissions(administrator=True)
    async def bytedaily_close(self, interaction: discord.Interaction) -> None:
        """Admin command: Close active poll immediately."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed("Permission Denied", "Only administrators can run this command."),
                ephemeral=True,
            )
            return

        open_poll = await poll_service.get_open_poll()
        if not open_poll:
            await interaction.followup.send(
                embed=make_error_embed("No Open Poll", "There is no currently active ByteDaily poll to close."),
                ephemeral=True,
            )
            return

        try:
            poll_id = open_poll['id']
            await self.scheduler._close_poll(poll_id)
            await interaction.followup.send(
                embed=make_success_embed(
                    "Poll Closed",
                    f"Successfully closed ByteDaily poll **#{poll_id}** and calculated results!",
                ),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: Error closing poll manually: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Close Error", f"Failed to close poll: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-add-question",
        description="[Admin] Add a new question to the ByteDaily question bank",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(
        correct_choice=[
            app_commands.Choice(name="A", value="A"),
            app_commands.Choice(name="B", value="B"),
            app_commands.Choice(name="C", value="C"),
            app_commands.Choice(name="D", value="D"),
        ]
    )
    async def bytedaily_add_question(
        self,
        interaction: discord.Interaction,
        question_text: str,
        choice_a: str,
        choice_b: str,
        choice_c: str,
        choice_d: str,
        correct_choice: app_commands.Choice[str],
        explanation: str = "",
        category: str = "",
    ) -> None:
        """Admin command: Add question to bank."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed("Permission Denied", "Only administrators can run this command."),
                ephemeral=True,
            )
            return

        try:
            tags = [category.strip()] if category and category.strip() else []
            new_id = await question_repo.insert(
                question_text=question_text.strip(),
                choice_a=choice_a.strip(),
                choice_b=choice_b.strip(),
                choice_c=choice_c.strip(),
                choice_d=choice_d.strip(),
                correct_answer=correct_choice.value,
                explanation=explanation.strip(),
                difficulty=1,
                tags=tags,
            )
            embed = make_success_embed(
                "Question Added",
                f"Successfully added question **#{new_id}** to `bd_questions`!",
            )
            embed.add_field(name="Question", value=question_text, inline=False)
            embed.add_field(name="Correct Answer", value=correct_choice.value, inline=True)
            if category:
                embed.add_field(name="Category", value=category, inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.error(f"ByteDaily: Error adding question: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Add Error", f"Failed to add question: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-status",
        description="[Admin] Check the system status of ByteDaily",
    )
    @app_commands.default_permissions(administrator=True)
    async def bytedaily_status(self, interaction: discord.Interaction) -> None:
        """Admin command: View ByteDaily status."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed("Permission Denied", "Only administrators can run this command."),
                ephemeral=True,
            )
            return

        try:
            open_poll = await poll_service.get_open_poll()
            closed_poll = await poll_service.get_closed_poll()
            active_questions = await question_repo.get_active_questions()
            total_users = await bd_db.fetchval("SELECT COUNT(*) FROM bd_users") or 0

            status_embed = make_info_embed(
                title="⚙️ ByteDaily System Status",
                description="Current state of ByteDaily database and scheduler.",
            )

            channel_mention = f"<#{BD_CHANNEL_ID}>" if BD_CHANNEL_ID else "⚠️ Not Configured"
            status_embed.add_field(name="Target Channel", value=channel_mention, inline=False)

            if open_poll:
                opened_at = open_poll.get("opened_at", "N/A")
                poll_info = f"**Open Poll #{open_poll['id']}** (Opened: {opened_at})"
            elif closed_poll:
                closed_at = closed_poll.get("closed_at", "N/A")
                poll_info = f"**Closed Poll #{closed_poll['id']}** (Awaiting Cleanup, Closed: {closed_at})"
            else:
                poll_info = "No Active Poll (Idle)"

            status_embed.add_field(name="Active Poll State", value=poll_info, inline=False)
            status_embed.add_field(name="Active Question Bank Size", value=str(len(active_questions)), inline=True)
            status_embed.add_field(name="Registered Users Count", value=str(total_users), inline=True)

            await interaction.followup.send(embed=status_embed, ephemeral=True)
        except Exception as e:
            log.error(f"ByteDaily: Error fetching status: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Status Error", f"Failed to fetch status: {e}"),
                ephemeral=True,
            )


    @app_commands.command(
        name="bytedaily-generate-ai",
        description="[Admin] Manually trigger AI question generation via Gemini (single API call)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(count="Number of questions to generate (default: 5, max: 10)")
    async def bytedaily_generate_ai(
        self,
        interaction: discord.Interaction,
        count: int = 5,
    ) -> None:
        """Admin command: Trigger AI question generation on demand."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed("Permission Denied", "Only administrators can run this command."),
                ephemeral=True,
            )
            return

        count = max(1, min(count, 10))  # clamp to [1, 10]

        try:
            inserted = await ai_generator_service.generate_and_store_questions(count=count)
            if inserted:
                await interaction.followup.send(
                    embed=make_success_embed(
                        "AI Generation Complete",
                        f"✅ Successfully generated and stored **{inserted}** new question(s) via Gemini API!",
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    embed=make_error_embed(
                        "Generation Failed",
                        "Gemini API returned 0 valid questions. Check `GEMINI_API_KEY` and API quota.",
                    ),
                    ephemeral=True,
                )
        except Exception as e:
            log.error(f"ByteDaily: Error in /bytedaily-generate-ai: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Generation Error", f"An unexpected error occurred: {e}"),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Entry point for bot.load_extension('features.bytedaily.cog')."""
    await bot.add_cog(ByteDailyCog(bot))
