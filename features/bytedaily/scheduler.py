"""
ByteDaily Scheduler — Manages the question lifecycle loop.

Uses discord.ext.tasks to run a 1-minute periodic loop with three phases:
  Phase 1 — POST:   Select a question, post embed + answer buttons (A–D),
                     pin it, and store current_question_message_id.
  Phase 2 — CLOSE:  After 12 hours, award points/streaks, then roll the
                     challenge channel window:
                       1) delete previous_result_message_id
                       2) delete current question → post Results embed
                          as the new previous_result_message_id
                       3) clear current_question_message_id
  Phase 3 — ADVANCE: After 12 more hours, mark the closed poll deleted
                     (results message is kept as the rolling previous
                     result) and post the next daily question.

Rolling window enforcement: the challenge channel may contain at most
  • 1 Active Question Embed (Pinned)
  • 1 Previous Poll Results Embed (Unpinned)

The scheduler evaluates timestamps on every 1-minute tick for crash/restart resilience.
DynamicItems are registered globally once on startup.

A separate daily loop fires at 00:00 UTC to pre-generate new questions via the
Gemini AI generator service (single API call, Free Tier safe).
"""

from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Dict, Optional, Union
import discord
from discord.ext import tasks

from bridge.legacy_adapter import log
from .constants import (
    ANSWER_WINDOW_SECONDS,
    CLEANUP_DELAY_SECONDS,
    POST_HOUR_UTC,
    BD_CHANNEL_ID,
)
from .database.repositories import poll_repo, settings_repo
from .embeds import build_challenge_embed, build_results_embed
from .services import (
    question_service,
    poll_service,
    ai_generator_service,
    leaderboard_service,
    rolling_window,
)
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

    async def _resolve_channel(
        self,
        channel_id: Optional[int] = None,
    ) -> Optional[Union[discord.TextChannel, discord.Thread]]:
        """Resolve a text channel from cache or API."""
        target_id = channel_id or BD_CHANNEL_ID
        if not target_id:
            return None
        channel = self.bot.get_channel(target_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(target_id)
            except Exception as e:
                log.error(f"ByteDaily: Could not fetch channel {target_id}: {e}")
                return None
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            log.error(f"ByteDaily: Channel {target_id} is not a text channel.")
            return None
        return channel

    async def _tick(self) -> None:
        """Core state machine evaluation executed every minute."""
        if not BD_CHANNEL_ID:
            return

        now = datetime.now(timezone.utc)

        # 1. Active OPEN poll check — close when ends_at is reached
        open_poll = await poll_service.get_open_poll()
        if open_poll:
            ends_at = poll_service.resolve_ends_at(open_poll)
            if now >= ends_at:
                log.info(
                    f"ByteDaily: Open poll #{open_poll['id']} ended "
                    f"(ends_at={ends_at.isoformat()}). Closing poll."
                )
                await self._close_poll(open_poll['id'])
            return

        # 2. Active CLOSED poll check (awaiting advance to next question)
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
                        f"({elapsed:.0f}s >= {CLEANUP_DELAY_SECONDS}s). Advancing cycle."
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
        """
        Step 3 of the roll — post the new active question, pin it, and track
        current_question_message_id. Keeps previous_result_message_id intact.
        """
        channel = target_channel or await self._resolve_channel()
        if not channel:
            log.error("ByteDaily: Could not find target channel for posting.")
            return

        question = await question_service.pick_next_question()

        # Create poll record first so the embed title can include poll_id
        now = datetime.now(timezone.utc)
        closes_at = now + timedelta(seconds=ANSWER_WINDOW_SECONDS)
        poll_id = await poll_service.create_poll(
            question_id=question['id'],
            channel_id=channel.id,
            message_id=None,
            ends_at=closes_at,
        )

        footer_icon = self.bot.user.display_avatar.url if self.bot.user else None
        embed = build_challenge_embed(
            question=question,
            poll_id=poll_id,
            closes_at=closes_at,
            participants=0,
            footer_icon_url=footer_icon,
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

        # Persist IDs: poll row + rolling-window current question
        await poll_service.update_message_ids(poll_id, message_id=msg.id)
        await rolling_window.save_current_question(msg.id)
        await question_service.record_asked(question_id=question["id"], poll_id=poll_id)

        # Enforce max 2 bot messages (keep current question + previous result only)
        if self.bot.user:
            await rolling_window.enforce_two_message_window(channel, self.bot.user)

        log.info(
            f"ByteDaily: Posted poll #{poll_id} for question #{question['id']} "
            f"in message {msg.id} (rolling window current set)."
        )

    async def _close_poll(self, poll_id: int) -> None:
        """
        Close voting + roll the challenge channel window:
          1) Delete oldest previous_result_message_id
          2) Delete current question → post fresh Results embed as previous_result
          3) Clear current_question_message_id (no active question until next post)
        """
        poll = await poll_repo.get_by_id(poll_id)
        if not poll:
            return

        stats = await poll_service.close_poll(poll_id)
        channel = await self._resolve_channel(poll.get('channel_id'))
        if not channel:
            return

        # Step 1 — purge the previous cycle's results embed
        await rolling_window.delete_previous_result(channel)

        # Step 2 — remove the active question embed (transition to results)
        await rolling_window.delete_current_question(
            channel,
            fallback_message_id=poll.get('message_id'),
        )

        question = await question_service.get_question_by_id(poll['question_id'])
        footer_icon = self.bot.user.display_avatar.url if self.bot.user else None
        stats_embed = build_results_embed(
            question=question,
            poll_id=poll_id,
            stats=stats,
            footer_icon_url=footer_icon,
        )

        result_view = ByteDailyResultView(poll_id=poll_id)
        stats_msg = await channel.send(embed=stats_embed, view=result_view)

        # Persist as the rolling previous_result (unpinned by default)
        await poll_service.update_message_ids(poll_id, stats_message_id=stats_msg.id)
        await rolling_window.save_previous_result(stats_msg.id)

        if self.bot.user:
            await rolling_window.enforce_two_message_window(channel, self.bot.user)

        log.info(
            f"ByteDaily: Closed poll #{poll_id} — results message {stats_msg.id} "
            "saved as previous_result_message_id."
        )

        # Refresh the live leaderboard now that points/streaks have been awarded
        await leaderboard_service.refresh_leaderboard_embed(self.bot)

    async def _delete_poll(self, poll_id: int) -> None:
        """
        Mark a closed poll as deleted in the DB.

        Discord results message is intentionally KEPT — it is the rolling
        previous_result_message_id until the next close cycle deletes it.
        The question message was already removed during _close_poll.
        """
        poll = await poll_repo.get_by_id(poll_id)
        if not poll:
            return

        # Safety: if a stale question message somehow remains and is NOT the
        # tracked previous_result, remove it. Never delete the rolling result.
        channel = await self._resolve_channel(poll.get('channel_id'))
        if channel:
            previous_id = await settings_repo.get_previous_result_message_id()
            question_msg_id = poll.get('message_id')
            if question_msg_id and question_msg_id != previous_id:
                await rolling_window.safe_delete_message(
                    channel, question_msg_id, label="stale_question"
                )

        await poll_service.mark_deleted(poll_id)
        log.info(
            f"ByteDaily: Marked poll #{poll_id} as deleted "
            "(previous_result embed retained in rolling window)."
        )

    async def force_cycle(
        self,
        *,
        reset_leaderboard_points: bool = False,
        target_channel: Optional[discord.TextChannel] = None,
    ) -> Dict[str, Any]:
        """
        Manually advance the full ByteDaily cycle in one shot:

          1. Close the active poll (award points, rolling-window results)
          2. Mark any closed poll as deleted (keep previous_result embed)
          3. Optionally reset bd_users points/streaks, then refresh leaderboard
          4. Post + pin a brand-new question (bypasses daily post-time gate)

        Returns a summary dict for the slash-command confirmation.
        """
        summary: Dict[str, Any] = {
            "closed_poll_id": None,
            "new_poll_id": None,
            "points_reset": False,
            "users_reset": 0,
        }

        # Step 1 — close active poll if present (results + rolling window)
        open_poll = await poll_service.get_open_poll()
        if open_poll:
            closed_id = open_poll["id"]
            log.info(f"ByteDaily force-cycle: Closing active poll #{closed_id}.")
            await self._close_poll(closed_id)
            await self._delete_poll(closed_id)
            summary["closed_poll_id"] = closed_id
        else:
            # Advance a leftover closed poll so the state machine is clean
            closed_poll = await poll_service.get_closed_poll()
            if closed_poll:
                closed_id = closed_poll["id"]
                log.info(
                    f"ByteDaily force-cycle: No open poll — marking closed poll "
                    f"#{closed_id} as deleted before posting next."
                )
                await self._delete_poll(closed_id)
                summary["closed_poll_id"] = closed_id

        # Step 3 — optional points reset, then always refresh leaderboard
        if reset_leaderboard_points:
            summary["users_reset"] = await poll_service.reset_leaderboard_points()
            summary["points_reset"] = True

        await leaderboard_service.refresh_leaderboard_embed(self.bot)

        # Step 4 — launch new poll immediately
        log.info("ByteDaily force-cycle: Posting new challenge.")
        await self._post_question(target_channel=target_channel)

        new_poll = await poll_service.get_open_poll()
        if new_poll:
            summary["new_poll_id"] = new_poll["id"]

        log.info(f"ByteDaily force-cycle complete: {summary}")
        return summary
