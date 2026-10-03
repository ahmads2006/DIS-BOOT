"""
ByteDaily Scheduler — Manages the question lifecycle loop.

Uses discord.ext.tasks to run a 1-minute periodic loop with three phases:
  Phase 1 — POST:   Select a question, post embed + answer buttons (A–D).
                     The poll is saved to bd_polls with status='open'.
  Phase 2 — CLOSE:  After 12 hours, close voting (disable buttons), award
                     points, update streaks via bd_upsert_user_stats RPC,
                     post a public stats summary message, add "Show my result"
                     button. Poll status set to 'closed'.
  Phase 3 — DELETE: After 12 more hours (24h total), delete the question message
                     and the stats message, set poll status to 'deleted', and
                     immediately post the next daily question.

The scheduler evaluates timestamps on every 1-minute tick for crash/restart resilience.
DynamicItems are registered globally once on startup.

A separate daily loop fires at 00:00 UTC to pre-generate new questions via the
Gemini AI generator service (single API call, Free Tier safe).
"""

from datetime import datetime, time as dt_time, timezone
from typing import Optional
import discord
from discord.ext import tasks

from bridge.legacy_adapter import log
from .constants import (
    ANSWER_WINDOW_SECONDS,
    CLEANUP_DELAY_SECONDS,
    POST_HOUR_UTC,
    BD_CHANNEL_ID,
    EMBED_COLOR_QUESTION,
    EMBED_COLOR_STATS,
)
from .database.repositories import poll_repo
from .services import question_service, poll_service, ai_generator_service, leaderboard_service
from .views import (
    ByteDailyAnswerView,
    ByteDailyResultView,
    DynamicAnswerButton,
    DynamicResultButton,
)


class ByteDailyScheduler:
    """Manages the 24-hour ByteDaily cycle using a 1-minute polling task."""

    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self._is_processing: bool = False
        self._dynamic_items_registered: bool = False

    def start(self) -> None:
        """Register dynamic items globally and start the 1-minute scheduler loop."""
        if not self._dynamic_items_registered:
            try:
                self.bot.add_dynamic_items(DynamicAnswerButton, DynamicResultButton)
                self._dynamic_items_registered = True
                log.info("ByteDaily: Registered DynamicItem classes globally with bot.")
            except Exception as e:
                log.error(f"ByteDaily: Failed to register dynamic items: {e}")

        if not self._check_loop.is_running():
            self._check_loop.start()
            log.info("ByteDaily: Scheduler loop started (1-minute polling interval).")

        if not self._midnight_generate.is_running():
            self._midnight_generate.start()
            log.info("ByteDaily: Midnight AI generation loop started (daily at 00:00 UTC).")

        if not BD_CHANNEL_ID:
            log.warning(
                "ByteDaily: BD_CHANNEL_ID is not set in environment variables. "
                "The scheduler will NOT post or close any polls until a channel is configured."
            )

    def stop(self) -> None:
        """Stop all scheduler loops."""
        if self._check_loop.is_running():
            self._check_loop.cancel()
            log.info("ByteDaily: Scheduler loop stopped.")

        if self._midnight_generate.is_running():
            self._midnight_generate.cancel()
            log.info("ByteDaily: Midnight AI generation loop stopped.")

    @tasks.loop(minutes=1)
    async def _check_loop(self) -> None:
        """Periodic loop checking poll state and triggering phase transitions."""
        if self._is_processing:
            return

        self._is_processing = True
        try:
            await self._tick()
        except Exception as e:
            log.error(f"ByteDaily: Error in scheduler loop tick: {e}", exc_info=True)
        finally:
            self._is_processing = False

    @_check_loop.before_loop
    async def _before_check_loop(self) -> None:
        """Wait until the Discord bot is fully ready before starting ticks."""
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ #
    # Midnight AI generation — fires once daily at 00:00 UTC              #
    # ------------------------------------------------------------------ #

    @tasks.loop(time=dt_time(hour=0, minute=0, tzinfo=timezone.utc))
    async def _midnight_generate(self) -> None:
        """
        Triggered once every day at 00:00 UTC.
        Calls ai_generator_service.generate_and_store_questions() to pre-seed
        the question bank using a single Gemini API request (Free Tier safe).
        Errors are logged but never allowed to crash the scheduler.
        """
        log.info("ByteDaily: Midnight generation task fired — requesting AI questions from Gemini.")
        try:
            inserted = await ai_generator_service.generate_and_store_questions(count=5)
            if inserted:
                log.info(f"ByteDaily: Midnight generation complete — {inserted} new question(s) added.")
            else:
                log.warning("ByteDaily: Midnight generation returned 0 questions (check GEMINI_API_KEY or API response).")
        except Exception as e:
            log.error(f"ByteDaily: Midnight generation task raised an unhandled exception: {e}", exc_info=True)

    @_midnight_generate.before_loop
    async def _before_midnight_generate(self) -> None:
        """Wait until the bot is ready before the midnight loop starts."""
        await self.bot.wait_until_ready()

    async def _tick(self) -> None:
        """Core state machine evaluation executed every minute."""
        if not BD_CHANNEL_ID:
            return

        now = datetime.now(timezone.utc)

        # 1. Active OPEN poll check
        open_poll = await poll_service.get_open_poll()
        if open_poll:
            opened_at = open_poll['opened_at']
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)
            elapsed = (now - opened_at).total_seconds()
            if elapsed >= ANSWER_WINDOW_SECONDS:
                log.info(
                    f"ByteDaily: Open poll #{open_poll['id']} window elapsed "
                    f"({elapsed:.0f}s >= {ANSWER_WINDOW_SECONDS}s). Closing poll."
                )
                await self._close_poll(open_poll['id'])
            return

        # 2. Active CLOSED poll check (awaiting cleanup)
        closed_poll = await poll_service.get_closed_poll()
        if closed_poll:
            closed_at = closed_poll['closed_at']
            if closed_at:
                if closed_at.tzinfo is None:
                    closed_at = closed_at.replace(tzinfo=timezone.utc)
                elapsed = (now - closed_at).total_seconds()
                if elapsed >= CLEANUP_DELAY_SECONDS:
                    log.info(
                        f"ByteDaily: Closed poll #{closed_poll['id']} cleanup delay elapsed "
                        f"({elapsed:.0f}s >= {CLEANUP_DELAY_SECONDS}s). Deleting and advancing."
                    )
                    await self._delete_poll(closed_poll['id'])
                    # If it's already post time today, immediately post next
                    await self._maybe_post_question(now)
            return

        # 3. No active poll (clean slate)
        await self._maybe_post_question(now)

    async def _maybe_post_question(self, now: datetime) -> None:
        """Check if today's post time has passed and no question was posted today."""
        if now.hour < POST_HOUR_UTC:
            return

        # Look up the latest poll by date to ensure we haven't already posted today
        latest_open = await poll_repo.get_latest_by_status('open')
        latest_closed = await poll_repo.get_latest_by_status('closed')
        latest_deleted = await poll_repo.get_latest_by_status('deleted')

        polls = [p for p in (latest_open, latest_closed, latest_deleted) if p is not None]
        if polls:
            polls.sort(key=lambda p: p['opened_at'], reverse=True)
            most_recent = polls[0]
            most_recent_opened_at = most_recent['opened_at']
            if most_recent_opened_at.tzinfo is None:
                most_recent_opened_at = most_recent_opened_at.replace(tzinfo=timezone.utc)
            if most_recent_opened_at.date() == now.date():
                # Already posted today
                return

        await self._post_question()

    async def _post_question(self, target_channel: Optional[discord.TextChannel] = None) -> None:
        """Pick next question, build embed + buttons, send message, and record poll."""
        channel = target_channel or (self.bot.get_channel(BD_CHANNEL_ID) if BD_CHANNEL_ID else None)
        if not channel:
            log.error("ByteDaily: Could not find target channel for posting.")
            return

        question = await question_service.pick_next_question()

        embed = discord.Embed(
            title="💡 ByteDaily — Daily Challenge",
            description=f"**{question['question_text']}**\n\n"
                        f"🇦 {question['choice_a']}\n"
                        f"🇧 {question['choice_b']}\n"
                        f"🇨 {question['choice_c']}\n"
                        f"🇩 {question['choice_d']}",
            color=EMBED_COLOR_QUESTION,
        )
        embed.set_footer(text=f"Difficulty: {'⭐' * question.get('difficulty', 1)} | Voting closes in 12 hours")

        # Create poll record in database
        poll_id = await poll_service.create_poll(
            question_id=question['id'],
            channel_id=channel.id,
            message_id=None,
        )

        view = ByteDailyAnswerView(poll_id=poll_id)
        msg = await channel.send(embed=embed, view=view)

        # Pin the challenge message so it stays visible
        try:
            await msg.pin()
            log.info(f"ByteDaily: Pinned challenge message {msg.id} in channel {channel.id}.")
        except discord.Forbidden:
            log.warning(
                f"ByteDaily: Cannot pin message {msg.id} — bot lacks 'Manage Messages' "
                f"permission in channel {channel.id}. Continuing without pin."
            )
        except Exception as e:
            log.warning(f"ByteDaily: Unexpected error pinning message {msg.id}: {e}")

        # Update message ID on poll record
        await poll_service.update_message_ids(poll_id, message_id=msg.id)
        log.info(f"ByteDaily: Posted poll #{poll_id} for question #{question['id']} in message {msg.id}")

    async def _close_poll(self, poll_id: int) -> None:
        """Close voting, award points, edit question message, and post stats message."""
        poll = await poll_repo.get_by_id(poll_id)
        if not poll:
            return

        stats = await poll_service.close_poll(poll_id)
        channel = self.bot.get_channel(poll['channel_id'])
        if not channel:
            return

        # Unpin and disable buttons on question message
        if poll.get('message_id'):
            try:
                msg = await channel.fetch_message(poll['message_id'])
                # Unpin before editing so the channel pin list is clean
                try:
                    await msg.unpin()
                    log.info(f"ByteDaily: Unpinned challenge message {msg.id} on poll close.")
                except discord.Forbidden:
                    log.warning(
                        f"ByteDaily: Cannot unpin message {msg.id} — bot lacks 'Manage Messages' permission."
                    )
                except Exception as e:
                    log.warning(f"ByteDaily: Unexpected error unpinning message {msg.id}: {e}")
                disabled_view = ByteDailyAnswerView(poll_id=poll_id)
                for child in disabled_view.children:
                    child.item.disabled = True
                await msg.edit(view=disabled_view)
            except discord.NotFound:
                log.warning(f"ByteDaily: Question message {poll['message_id']} not found to disable.")
            except Exception as e:
                log.error(f"ByteDaily: Error disabling buttons on message {poll['message_id']}: {e}")

        # Post stats message with "Show my result" button
        question = await question_service.get_question_by_id(poll['question_id'])
        stats_embed = discord.Embed(
            title="📊 ByteDaily — Challenge Results",
            description=f"Voting for today's challenge is now closed!\n\n"
                        f"**Correct Answer:** {question['correct_answer']}\n\n"
                        f"**Explanation:**\n{question['explanation']}\n\n"
                        f"👥 **Total Participants:** {stats['total']}\n"
                        f"✅ **Correct Answers:** {stats['correct']} ({stats['percent_correct']}%)\n"
                        f"❌ **Wrong Answers:** {stats['wrong']}",
            color=EMBED_COLOR_STATS,
        )
        stats_embed.set_footer(text="Click below to see your personal result. Cleanup in 12 hours.")

        result_view = ByteDailyResultView(poll_id=poll_id)
        stats_msg = await channel.send(embed=stats_embed, view=result_view)

        await poll_service.update_message_ids(poll_id, stats_message_id=stats_msg.id)
        log.info(f"ByteDaily: Closed poll #{poll_id}, posted stats message {stats_msg.id}")

        # Refresh the live leaderboard now that points/streaks have been awarded
        await leaderboard_service.refresh_leaderboard_embed(self.bot)

    async def _delete_poll(self, poll_id: int) -> None:
        """Delete Discord messages and mark poll as deleted in DB."""
        poll = await poll_repo.get_by_id(poll_id)
        if not poll:
            return

        channel = self.bot.get_channel(poll['channel_id'])
        if channel:
            if poll.get('message_id'):
                try:
                    msg = await channel.fetch_message(poll['message_id'])
                    # Unpin before deleting (best-effort; message may already be unpinned)
                    try:
                        await msg.unpin()
                    except (discord.Forbidden, discord.NotFound):
                        pass
                    except Exception:
                        pass
                    await msg.delete()
                except discord.NotFound:
                    pass
                except Exception as e:
                    log.warning(f"ByteDaily: Failed to delete question message {poll['message_id']}: {e}")

            if poll.get('stats_message_id'):
                try:
                    stats_msg = await channel.fetch_message(poll['stats_message_id'])
                    await stats_msg.delete()
                except discord.NotFound:
                    pass
                except Exception as e:
                    log.warning(f"ByteDaily: Failed to delete stats message {poll['stats_message_id']}: {e}")

        await poll_service.mark_deleted(poll_id)
        log.info(f"ByteDaily: Cleaned up poll #{poll_id} messages and marked as deleted.")
