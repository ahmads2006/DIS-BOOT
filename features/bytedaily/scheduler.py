"""
ByteDaily Scheduler — Continuous Dynamic Rolling Cycle.

Lifecycle is driven purely by each poll's `ends_at` timestamp
(default: publication time + ANSWER_WINDOW_SECONDS). There is no
fixed wall-clock post hour (e.g. 3 AM / 12 PM) and no second
12-hour cleanup wait.

Automated handover when `ends_at` is reached:
  1. Close the active poll (award points, rolling-window results)
  2. Mark it deleted (keep previous_result embed)
  3. Immediately post the next unused question with a fresh ends_at
  4. Sleep until that new ends_at, then repeat

Restart resiliency:
  - If active ends_at is in the future → wait the remaining time
  - If active ends_at is already past → rollover immediately
  - If no open poll → post one immediately

DynamicItems are registered globally once on startup.
A separate daily loop at 00:00 UTC pre-generates AI questions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Dict, Optional, Union

import discord
from discord.ext import tasks

from bridge.legacy_adapter import log
from .constants import ANSWER_WINDOW_SECONDS, BD_CHANNEL_ID
from .database.repositories import poll_repo, settings_repo, answer_repo
from .embeds import (
    build_challenge_embed,
    build_results_embed,
    build_personal_result_dm_embed,
)
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

# Re-check ends_at at least this often so /bytedaily-extend|reduce take effect promptly
_WAKE_CHUNK_SECONDS = 30.0
# If nothing is open and posting fails, back off before retrying
_EMPTY_RETRY_SECONDS = 60.0


class ByteDailyScheduler:
    """Continuous ends_at-driven challenge cycle (no wall-clock schedule)."""

    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self._is_processing: bool = False
        self._dynamic_items_registered: bool = False
        self._cycle_task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._wake_event: asyncio.Event = asyncio.Event()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def register_dynamic_items(self) -> None:
        """
        Register DynamicItem handlers ASAP (before DB init / heavy work).
        Must be ready before any button click arrives from Discord.
        """
        if self._dynamic_items_registered:
            return
        try:
            self.bot.add_dynamic_items(DynamicAnswerButton, DynamicResultButton)
            self._dynamic_items_registered = True
            log.info("ByteDaily: Registered DynamicItem classes globally with bot.")
        except Exception as e:
            log.error(f"ByteDaily: Failed to register dynamic items: {e}")

    def start(self) -> None:
        """Register dynamic items (if needed) and start the continuous rolling cycle."""
        self.register_dynamic_items()

        self._stop_event.clear()
        if self._cycle_task is None or self._cycle_task.done():
            self._cycle_task = asyncio.create_task(
                self._continuous_cycle(),
                name="bytedaily-continuous-cycle",
            )
            log.info(
                "ByteDaily: Continuous rolling cycle started "
                "(driven by poll ends_at, not wall-clock hours)."
            )

        if not self._midnight_generate.is_running():
            self._midnight_generate.start()
            log.info("ByteDaily: Midnight AI generation loop started (daily at 00:00 UTC).")

        if not BD_CHANNEL_ID:
            log.warning(
                "ByteDaily: BD_CHANNEL_ID is not set in environment variables. "
                "The scheduler will NOT post or close any polls until a channel is configured."
            )

    def stop(self) -> None:
        """Stop the continuous cycle and midnight generation loop."""
        self._stop_event.set()
        self._wake_event.set()  # unblock any pending sleep
        if self._cycle_task and not self._cycle_task.done():
            self._cycle_task.cancel()
            log.info("ByteDaily: Continuous rolling cycle stopped.")
        self._cycle_task = None

        if self._midnight_generate.is_running():
            self._midnight_generate.cancel()
            log.info("ByteDaily: Midnight AI generation loop stopped.")

    def nudge(self) -> None:
        """Wake the cycle early (e.g. after force-cycle / duration change)."""
        self._wake_event.set()

    # ------------------------------------------------------------------ #
    # Continuous cycle                                                     #
    # ------------------------------------------------------------------ #

    async def _continuous_cycle(self) -> None:
        """
        Main loop:
          ensure active poll → sleep until ends_at → rollover → repeat.
        Survives restarts by reading ends_at from Supabase on every wake.
        """
        await self.bot.wait_until_ready()
        log.info("ByteDaily: Bot ready — evaluating active challenge ends_at.")

        # Re-attach answer buttons on the live challenge message after restart
        try:
            await self.rebind_active_challenge_view()
        except Exception as e:
            log.warning(f"ByteDaily: Could not rebind active challenge view: {e}")

        while not self._stop_event.is_set():
            if not BD_CHANNEL_ID:
                await self._interruptible_sleep(_EMPTY_RETRY_SECONDS)
                continue

            if self._is_processing:
                await self._interruptible_sleep(1.0)
                continue

            self._is_processing = True
            try:
                delay = await self._cycle_step()
            except Exception as e:
                log.error(f"ByteDaily: Error in continuous cycle step: {e}", exc_info=True)
                delay = _EMPTY_RETRY_SECONDS
            finally:
                self._is_processing = False

            if self._stop_event.is_set():
                break
            await self._interruptible_sleep(delay)

    async def rebind_active_challenge_view(self) -> None:
        """
        After restart: edit the open poll's Discord message with a fresh AnswerView
        so button interactions are routed to this process's DynamicItems.
        """
        open_poll = await poll_service.get_open_poll()
        if not open_poll or not open_poll.get("message_id"):
            return

        channel = await self._resolve_channel(open_poll.get("channel_id"))
        if not channel:
            return

        try:
            msg = await channel.fetch_message(int(open_poll["message_id"]))
            view = ByteDailyAnswerView(poll_id=int(open_poll["id"]), disabled=False)
            await msg.edit(view=view)
            log.info(
                f"ByteDaily: Rebound answer buttons on message {msg.id} "
                f"for open poll #{open_poll['id']}."
            )
        except discord.NotFound:
            log.warning(
                f"ByteDaily: Open poll #{open_poll['id']} message "
                f"{open_poll.get('message_id')} not found for view rebind."
            )
        except Exception as e:
            log.warning(f"ByteDaily: Failed rebinding challenge view: {e}")

    async def _cycle_step(self) -> float:
        """
        One evaluation of scheduler state.
        Returns how many seconds to sleep before the next evaluation.
        """
        now = datetime.now(timezone.utc)

        open_poll = await poll_service.get_open_poll()
        if open_poll:
            ends_at = poll_service.resolve_ends_at(open_poll)
            delay = (ends_at - now).total_seconds()

            if delay <= 0:
                log.info(
                    f"ByteDaily: Poll #{open_poll['id']} ends_at reached "
                    f"({ends_at.isoformat()}) — starting automated handover."
                )
                await self._rollover(open_poll["id"])
                return 1.0  # briefly yield, then wait on the new poll's ends_at

            chunk = min(delay, _WAKE_CHUNK_SECONDS)
            log.debug(
                f"ByteDaily: Poll #{open_poll['id']} live — "
                f"{delay:.0f}s until ends_at; sleeping {chunk:.0f}s."
            )
            return chunk

        # No open poll — finish any leftover closed poll, then post immediately
        closed_poll = await poll_service.get_closed_poll()
        if closed_poll:
            log.info(
                f"ByteDaily: Found leftover closed poll #{closed_poll['id']} — "
                "marking deleted and posting next challenge immediately."
            )
            await self._delete_poll(closed_poll["id"])

        log.info("ByteDaily: No active challenge — posting next question now.")
        await self._post_question()
        return 1.0

    async def _rollover(self, poll_id: int) -> None:
        """Close → delete → immediately launch the next challenge."""
        await self._close_poll(poll_id)
        await self._delete_poll(poll_id)
        await self._post_question()
        log.info(f"ByteDaily: Handover complete after poll #{poll_id}.")

    async def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep up to `seconds`, but wake early on stop/nudge."""
        if seconds <= 0:
            return
        self._wake_event.clear()
        try:
            await asyncio.wait_for(self._wake_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    # ------------------------------------------------------------------ #
    # Midnight AI generation — fires once daily at 00:00 UTC              #
    # ------------------------------------------------------------------ #

    @tasks.loop(time=dt_time(hour=0, minute=0, tzinfo=timezone.utc))
    async def _midnight_generate(self) -> None:
        """Pre-seed the question bank via Gemini (Free Tier safe)."""
        log.info("ByteDaily: Midnight generation task fired — requesting AI questions from Gemini.")
        try:
            inserted = await ai_generator_service.generate_and_store_questions(count=5)
            if inserted:
                log.info(f"ByteDaily: Midnight generation complete — {inserted} new question(s) added.")
            else:
                log.warning(
                    "ByteDaily: Midnight generation returned 0 questions "
                    "(check GEMINI_API_KEY or API response)."
                )
        except Exception as e:
            log.error(
                f"ByteDaily: Midnight generation task raised an unhandled exception: {e}",
                exc_info=True,
            )

    @_midnight_generate.before_loop
    async def _before_midnight_generate(self) -> None:
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ #
    # Channel / Discord helpers                                            #
    # ------------------------------------------------------------------ #

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

    async def _post_question(self, target_channel: Optional[discord.TextChannel] = None) -> None:
        """
        Post a new active question, pin it, and track current_question_message_id.
        ends_at = now + ANSWER_WINDOW_SECONDS (default 12h from publication).
        """
        channel = target_channel or await self._resolve_channel()
        if not channel:
            log.error("ByteDaily: Could not find target channel for posting.")
            return

        question = await question_service.pick_next_question()

        now = datetime.now(timezone.utc)
        closes_at = now + timedelta(seconds=ANSWER_WINDOW_SECONDS)
        poll_id = await poll_service.create_poll(
            question_id=question["id"],
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

        await poll_service.update_message_ids(poll_id, message_id=msg.id)
        await rolling_window.save_current_question(msg.id)
        await question_service.record_asked(question_id=question["id"], poll_id=poll_id)

        if self.bot.user:
            await rolling_window.enforce_two_message_window(channel, self.bot.user)

        log.info(
            f"ByteDaily: Posted poll #{poll_id} for question #{question['id']} "
            f"in message {msg.id} (ends_at={closes_at.isoformat()})."
        )
        self.nudge()

    async def _close_poll(self, poll_id: int) -> None:
        """
        Close voting + roll the challenge channel window:
          1) Delete oldest previous_result_message_id
          2) Delete current question → post Results embed as previous_result
          3) Clear current_question_message_id
          4) DM each participant a personal score report (graceful if DMs closed)
        """
        poll = await poll_repo.get_by_id(poll_id)
        if not poll:
            return

        stats = await poll_service.close_poll(poll_id)
        question = await question_service.get_question_by_id(poll["question_id"])
        footer_icon = self.bot.user.display_avatar.url if self.bot.user else None

        channel = await self._resolve_channel(poll.get("channel_id"))
        if channel:
            await rolling_window.delete_previous_result(channel)
            await rolling_window.delete_current_question(
                channel,
                fallback_message_id=poll.get("message_id"),
            )

            stats_embed = build_results_embed(
                question=question,
                poll_id=poll_id,
                stats=stats,
                footer_icon_url=footer_icon,
            )

            result_view = ByteDailyResultView(poll_id=poll_id)
            stats_msg = await channel.send(embed=stats_embed, view=result_view)

            await poll_service.update_message_ids(poll_id, stats_message_id=stats_msg.id)
            await rolling_window.save_previous_result(stats_msg.id)

            if self.bot.user:
                await rolling_window.enforce_two_message_window(channel, self.bot.user)

            log.info(
                f"ByteDaily: Closed poll #{poll_id} — results message {stats_msg.id} "
                "saved as previous_result_message_id."
            )
        else:
            log.warning(
                f"ByteDaily: Channel missing for poll #{poll_id} — "
                "skipping public results message; still sending personal DMs."
            )

        # Personal DM reports (does not replace the public channel summary)
        await self._dm_personal_results(
            poll_id=poll_id,
            question=question,
            footer_icon_url=footer_icon,
        )

        await leaderboard_service.refresh_leaderboard_embed(self.bot)

    async def _dm_personal_results(
        self,
        *,
        poll_id: int,
        question: Dict[str, Any],
        footer_icon_url: Optional[str] = None,
    ) -> None:
        """
        After poll close: DM every participant a structured personal result embed.
        Groups answers by user_id; skips users with closed DMs (Forbidden).
        """
        answers = await answer_repo.get_all_for_poll(poll_id)
        if not answers:
            log.info(f"ByteDaily: Poll #{poll_id} has no answers — skipping result DMs.")
            return

        # Group by Discord user_id (one answer per user per poll today)
        by_user: Dict[int, List[Dict[str, Any]]] = {}
        for row in answers:
            uid = int(row["user_id"])
            by_user.setdefault(uid, []).append(row)

        sent = 0
        skipped_forbidden = 0
        failed = 0

        for user_id, user_answers in by_user.items():
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            except Exception as e:
                failed += 1
                log.warning(f"ByteDaily: Could not fetch user {user_id} for result DM: {e}")
                continue

            correct_count = sum(1 for a in user_answers if a.get("is_correct"))
            total_questions = len(user_answers)
            # Primary answer for the (single) question in this poll
            primary = user_answers[0]
            embed = build_personal_result_dm_embed(
                poll_id=poll_id,
                question=question,
                chosen_answer=str(primary.get("chosen_answer") or "?"),
                is_correct=bool(primary.get("is_correct")),
                correct_count=correct_count,
                total_questions=total_questions,
                footer_icon_url=footer_icon_url,
            )

            try:
                await user.send(embed=embed)
                sent += 1
            except discord.Forbidden:
                skipped_forbidden += 1
                log.info(
                    f"ByteDaily: Cannot DM result to user {user_id} — DMs closed/blocked."
                )
            except Exception as e:
                failed += 1
                log.warning(f"ByteDaily: Failed sending result DM to user {user_id}: {e}")

            # Light pacing to avoid Discord rate limits on large participant sets
            await asyncio.sleep(0.35)

        log.info(
            f"ByteDaily: Poll #{poll_id} personal result DMs — "
            f"sent={sent}, dm_closed={skipped_forbidden}, failed={failed}, "
            f"participants={len(by_user)}."
        )

    async def _delete_poll(self, poll_id: int) -> None:
        """
        Mark a closed poll as deleted in the DB.
        Discord results message is kept as previous_result_message_id.
        """
        poll = await poll_repo.get_by_id(poll_id)
        if not poll:
            return

        channel = await self._resolve_channel(poll.get("channel_id"))
        if channel:
            previous_id = await settings_repo.get_previous_result_message_id()
            question_msg_id = poll.get("message_id")
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
        Manually advance the full ByteDaily cycle in one shot.
        Wakes the continuous loop afterward so it tracks the new ends_at.
        """
        summary: Dict[str, Any] = {
            "closed_poll_id": None,
            "new_poll_id": None,
            "points_reset": False,
            "users_reset": 0,
        }

        open_poll = await poll_service.get_open_poll()
        if open_poll:
            closed_id = open_poll["id"]
            log.info(f"ByteDaily force-cycle: Closing active poll #{closed_id}.")
            await self._close_poll(closed_id)
            await self._delete_poll(closed_id)
            summary["closed_poll_id"] = closed_id
        else:
            closed_poll = await poll_service.get_closed_poll()
            if closed_poll:
                closed_id = closed_poll["id"]
                log.info(
                    f"ByteDaily force-cycle: No open poll — marking closed poll "
                    f"#{closed_id} as deleted before posting next."
                )
                await self._delete_poll(closed_id)
                summary["closed_poll_id"] = closed_id

        if reset_leaderboard_points:
            summary["users_reset"] = await poll_service.reset_leaderboard_points()
            summary["points_reset"] = True

        await leaderboard_service.refresh_leaderboard_embed(self.bot)

        log.info("ByteDaily force-cycle: Posting new challenge.")
        await self._post_question(target_channel=target_channel)

        new_poll = await poll_service.get_open_poll()
        if new_poll:
            summary["new_poll_id"] = new_poll["id"]

        self.nudge()
        log.info(f"ByteDaily force-cycle complete: {summary}")
        return summary
