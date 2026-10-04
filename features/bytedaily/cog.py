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
from .constants import BD_CHANNEL_ID, BD_LEADERBOARD_CHANNEL_ID
from .database.client import bd_db
from .database.repositories import question_repo, user_repo
from .scheduler import ByteDailyScheduler
from .services import poll_service, question_service, stats_service, ai_generator_service, leaderboard_service


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

    @app_commands.command(name="leaderboard", description="عرض قائمة المتصدرين وأعلى النقاط في ByteDaily")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        """
        Public command: refresh the single static #leaderboard message in-place,
        then show an ephemeral snapshot (never posts a duplicate in the channel).
        """
        await interaction.response.defer(ephemeral=True)
        try:
            # Keep the pinned #leaderboard message as the single source of truth
            await leaderboard_service.refresh_leaderboard_embed(self.bot)

            top_users = await user_repo.get_leaderboard(limit=10)
            embed = leaderboard_service.build_leaderboard_embed(top_users)

            lb_channel = self.bot.get_channel(BD_LEADERBOARD_CHANNEL_ID) if BD_LEADERBOARD_CHANNEL_ID else None
            channel_hint = (
                f"\n📌 اللوحة المباشرة: {lb_channel.mention}"
                if lb_channel
                else (
                    f"\n📌 اللوحة المباشرة: <#{BD_LEADERBOARD_CHANNEL_ID}>"
                    if BD_LEADERBOARD_CHANNEL_ID
                    else ""
                )
            )
            if channel_hint:
                embed.description = (embed.description or "") + channel_hint

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.error(f"ByteDaily: /leaderboard error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Error", f"Failed to fetch leaderboard: {e}"),
                ephemeral=True,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Admin Slash Commands
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="bytedaily-post",
        description="[أدمن] نشر تحدي ByteDaily جديد في القناة فوراً",
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
        description="[أدمن] إغلاق التحدي النشط حالياً وحساب النتائج والـ Streaks",
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
        description="[أدمن] إضافة سؤال جديد يدوياً إلى بنك أسئلة ByteDaily",
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
        description="[أدمن] عرض حالة نظام ByteDaily والإحصائيات الحالية",
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
            total_users = await user_repo.get_total_users()

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
        name="bytedaily-generate",
        description="[أدمن] توليد أسئلة برمجة فوراً باستخدام الذكاء الاصطناعي وإضافتها لبنك الأسئلة",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(count="عدد الأسئلة المطلوب توليدها (الافتراضي: 5، الحد الأقصى: 10)")
    async def bytedaily_generate(
        self,
        interaction: discord.Interaction,
        count: int = 5,
    ) -> None:
        """Admin command: On-demand AI question generation via Gemini."""
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
                embed = make_success_embed(
                    "AI Generation Complete",
                    f"✅ Successfully generated and stored **{inserted}** question(s) into `bd_questions` via Gemini!",
                )
                embed.add_field(name="Requested", value=str(count), inline=True)
                embed.add_field(name="Inserted", value=str(inserted), inline=True)
            else:
                embed = make_error_embed(
                    "Generation Failed",
                    "Gemini returned 0 valid questions.\n"
                    "Check `GEMINI_API_KEY` in `.env` and Gemini API quota/availability.",
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.error(f"ByteDaily: Error in /bytedaily-generate: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Generation Error", f"An unexpected error occurred: `{e}`"),
                ephemeral=True,
            )


    # ─────────────────────────────────────────────────────────────────────────
    # Live Leaderboard & Personal Rank
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="bytedaily-leaderboard",
        description="[أدمن] تحديث لوحة المتصدرين الثابتة فوراً في قناة اللوحة",
    )
    @app_commands.default_permissions(administrator=True)
    async def bytedaily_leaderboard_refresh(self, interaction: discord.Interaction) -> None:
        """Admin command: Force an immediate leaderboard embed refresh."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed("Permission Denied", "Only administrators can run this command."),
                ephemeral=True,
            )
            return

        if not BD_LEADERBOARD_CHANNEL_ID:
            await interaction.followup.send(
                embed=make_error_embed(
                    "Not Configured",
                    "BD_LEADERBOARD_CHANNEL_ID is not set in `.env`. Add it to enable the live leaderboard.",
                ),
                ephemeral=True,
            )
            return

        try:
            await leaderboard_service.refresh_leaderboard_embed(self.bot)
            lb_channel = self.bot.get_channel(BD_LEADERBOARD_CHANNEL_ID)
            channel_mention = lb_channel.mention if lb_channel else f"<#{BD_LEADERBOARD_CHANNEL_ID}>"
            await interaction.followup.send(
                embed=make_success_embed(
                    "Leaderboard Refreshed",
                    f"✅ Live leaderboard has been updated in {channel_mention}.",
                ),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: Error refreshing leaderboard: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Refresh Error", f"Failed to refresh leaderboard: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-rank",
        description="عرض إحصائياتك الشخصية ورتبتك في تحدي ByteDaily",
    )
    async def bytedaily_rank(self, interaction: discord.Interaction) -> None:
        """Public command: Show the caller's personal ByteDaily stats card."""
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        try:
            stats = await user_repo.get_by_id(user_id)
            if not stats:
                await interaction.followup.send(
                    embed=make_info_embed(
                        title="📊 بياناتك في ByteDaily",
                        description=(
                            "لم تشارك في أي تحدٍّ بعد!\n"
                            "حل التحدي اليومي للبدء في تجميع النقاط والترتيب. 🚀"
                        ),
                    ),
                    ephemeral=True,
                )
                return

            rank = await user_repo.get_rank(user_id)
            total_users = await user_repo.get_total_users()

            correct = int(stats.get("correct_count", 0))
            wrong = int(stats.get("wrong_count", 0))
            total_ans = correct + wrong
            accuracy = f"{round(correct / total_ans * 100)}%" if total_ans > 0 else "—"
            current_streak = stats.get("current_streak", 0)
            best_streak = stats.get("best_streak", 0)
            points = stats.get("total_points", 0)
            rank_str = f"#{rank}" if rank else "—"

            embed = discord.Embed(
                title=f"📊 إحصائياتك في ByteDaily",
                color=discord.Color.blurple(),
            )
            embed.set_author(
                name=str(interaction.user),
                icon_url=interaction.user.display_avatar.url,
            )
            embed.add_field(
                name="🏅 الترتيب",
                value=f"**{rank_str}** من أصل {total_users} مشارك",
                inline=True,
            )
            embed.add_field(
                name="⭐ النقاط",
                value=f"**{points}** pts",
                inline=True,
            )
            embed.add_field(
                name="🔥 السلسلة الحالية / الأفضل",
                value=f"**{current_streak}** / **{best_streak}**",
                inline=True,
            )
            embed.add_field(
                name="✅ إجابات صحيحة",
                value=f"**{correct}** / {total_ans}",
                inline=True,
            )
            embed.add_field(
                name="🎯 نسبة الدقة",
                value=accuracy,
                inline=True,
            )
            embed.add_field(
                name="❌ إجابات خاطئة",
                value=str(wrong),
                inline=True,
            )
            embed.set_footer(text="أحل التحدي اليومي لتحسين ترتيبك!")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            log.error(f"ByteDaily: /bytedaily-rank error for user {user_id}: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ", f"فشل جلب إحصائياتك: {e}"),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Entry point for bot.load_extension('features.bytedaily.cog')."""
    await bot.add_cog(ByteDailyCog(bot))
