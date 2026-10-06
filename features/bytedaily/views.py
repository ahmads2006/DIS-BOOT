"""
ByteDaily Views — Discord UI components for the daily question.

Uses discord.ui.DynamicItem for persistent, leak-free button handling:
  1. DynamicAnswerButton: Handles A, B, C, D choices via regex template.
  2. DynamicResultButton: Handles 'Show my result' button via regex template.

Views:
  - ByteDailyAnswerView: Container for the 4 dynamic answer buttons when sending.
  - ByteDailyResultView: Container for the dynamic result button when sending.

Callbacks ALWAYS call interaction.response.defer(ephemeral=True) as the first
line of the body so Discord never shows "The application didn't respond in time",
then reply exclusively via interaction.followup.send().
"""

import asyncio
import re
from typing import Any, Dict, Optional
import discord
from discord.ui import Button, DynamicItem, View

from bridge.legacy_adapter import log
from core.sentry import capture_interaction_error
from .constants import (
    BD_CHANNEL_ID,
    CUSTOM_ID_PREFIX_ANSWER,
    CUSTOM_ID_PREFIX_RESULT,
    CUSTOM_ID_PREFIX_TRANSLATE,
    EMBED_COLOR_CORRECT,
    EMBED_COLOR_WRONG,
    ROLE_ARABIC,
    ROLE_ENGLISH,
)
from .database.repositories import answer_repo, poll_repo, question_repo, user_repo
from .services import poll_service
from .embeds import (
    build_challenge_embed,
    build_english_challenge_embed,
    build_streak_milestone_embed,
)


_GENERIC_ANSWER_ERROR = "⚠️ حدث خطأ في معالجة الإجابة، يرجى المحاولة مرة أخرى. | An error occurred while processing your answer, please try again."
_GENERIC_RESULT_ERROR = "⚠️ حدث خطأ في جلب النتيجة، يرجى المحاولة مرة أخرى. | An error occurred while fetching your result, please try again."

_PENDING_EMBED_UPDATES: Dict[int, asyncio.Task] = {}
_UPDATE_LOCK: asyncio.Lock = asyncio.Lock()


async def schedule_debounced_poll_refresh(
    channel: Any,
    poll_id: int,
    poll: Dict[str, Any],
    question: Dict[str, Any],
    footer_icon_url: Optional[str] = None,
    delay: float = 3.0,
) -> None:
    """
    Debounce public message embed edits to prevent hitting Discord HTTP 429 rate limits.
    Coalesces rapid successive votes into a single edit every `delay` seconds.
    """
    import asyncio as _asyncio
    async with _UPDATE_LOCK:
        existing_task = _PENDING_EMBED_UPDATES.get(poll_id)
        if existing_task and not existing_task.done():
            return

        async def _do_refresh():
            try:
                await _asyncio.sleep(delay)
                counts = await answer_repo.count_for_poll(poll_id)
                closes_at = poll_service.resolve_ends_at(poll)
                embed = build_challenge_embed(
                    question=question,
                    poll_id=poll_id,
                    closes_at=closes_at,
                    participants=counts.get("total", 0),
                    footer_icon_url=footer_icon_url,
                )
                message_id = poll.get("message_id")
                if channel and message_id:
                    msg = await channel.fetch_message(message_id)
                    await msg.edit(embed=embed)
            except Exception as e:
                log.warning(f"ByteDaily: Debounced refresh error on poll #{poll_id}: {e}")
            finally:
                async with _UPDATE_LOCK:
                    _PENDING_EMBED_UPDATES.pop(poll_id, None)

        task = _asyncio.create_task(_do_refresh(), name=f"debounced-poll-refresh-{poll_id}")
        _PENDING_EMBED_UPDATES[poll_id] = task


async def _defer_ephemeral(interaction: discord.Interaction) -> bool:
    """
    Acknowledge the interaction immediately. Returns False if the token expired
    or Discord rejected the defer (caller should return without DB/network work).
    """
    try:
        if interaction.response.is_done():
            return True
        await interaction.response.defer(ephemeral=True)
        return True
    except (discord.NotFound, discord.HTTPException) as e:
        log.warning(f"ByteDaily: Could not defer interaction: {e}")
        return False


def resolve_user_language(
    interaction: discord.Interaction,
    user_db_profile: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Resolve user language with a 3-tier priority system:
      - Priority 1 (Database preference): If user_db_profile contains a valid value
        for 'preferred_language' ('ar' or 'en', case-insensitive), return it.
      - Priority 2 (Discord roles): Check interaction.user.roles:
        - If the user has a role named 'English' (case-insensitive) and does not have an 'Arabic' role, return 'en'.
        - If the user has a role named 'Arabic' (case-insensitive) and does not have an 'English' role, return 'ar'.
      - Priority 3 (Conflict / Fallback): If the user has both roles or neither role, default to 'ar'.
    """
    # Priority 1: Explicit database preference
    if user_db_profile and isinstance(user_db_profile, dict):
        pref = user_db_profile.get("preferred_language")
        if pref and isinstance(pref, str):
            pref_clean = pref.strip().lower()
            if pref_clean in ("ar", "en"):
                return pref_clean

    # Priority 2: Discord member roles
    roles = []
    try:
        user = interaction.user
        if hasattr(user, "roles") and user.roles:
            roles = [r.name.strip().lower() for r in user.roles if hasattr(r, "name")]
        elif interaction.guild and hasattr(interaction.guild, "get_member") and user:
            member = interaction.guild.get_member(user.id)
            if member and hasattr(member, "roles") and member.roles:
                roles = [r.name.strip().lower() for r in member.roles if hasattr(r, "name")]
    except Exception as e:
        log.warning(f"ByteDaily: Error accessing member roles for language resolution: {e}")
        roles = []

    target_english = ROLE_ENGLISH.strip().lower()
    target_arabic = ROLE_ARABIC.strip().lower()

    has_english = any(r == target_english for r in roles)
    has_arabic = any(r == target_arabic for r in roles)

    if has_english and not has_arabic:
        return "en"
    if has_arabic and not has_english:
        return "ar"

    # Priority 3: Conflict (both roles) or Fallback (neither role)
    return "ar"



# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Buttons (Registered ONCE globally on bot startup)
# ─────────────────────────────────────────────────────────────────────────────

class DynamicAnswerButton(
    DynamicItem[Button],
    template=r"bd_answer_(?P<poll_id>[0-9]+)_(?P<choice>[A-D])",
):
    """Persistent dynamic button for answering A, B, C, or D."""

    def __init__(
        self,
        poll_id: int,
        choice: str,
        disabled: bool = False,
        row: Optional[int] = None,
    ) -> None:
        # Plain letter labels only. Regional-indicator emojis (🇦) render as "A"
        # and combined with label="A" show as "A A" in Discord.
        super().__init__(
            Button(
                label=choice.upper(),
                style=discord.ButtonStyle.primary,
                custom_id=f"{CUSTOM_ID_PREFIX_ANSWER}{poll_id}_{choice}",
                disabled=disabled,
                row=row,
            )
        )
        self.poll_id = poll_id
        self.choice = choice

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: Button,
        match: re.Match[str],
        /,
    ) -> "DynamicAnswerButton":
        return cls(poll_id=int(match.group("poll_id")), choice=match.group("choice"))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _defer_ephemeral(interaction):
            return

        # Fetch user's profile and resolve language preference via 3-tier resolution
        user_db_profile = await user_repo.get_by_id(interaction.user.id)
        lang = resolve_user_language(interaction, user_db_profile)
        is_en = lang == "en"

        # Process answer + respond via followup (never response.send_message)
        try:
            poll = await poll_repo.get_by_id(self.poll_id)
            if not poll or poll.get("status") != "open":
                msg_closed = (
                    "⚠️ This challenge is already closed. Answers are no longer accepted."
                    if is_en
                    else "⚠️ تم إغلاق هذا التحدي بالفعل، لم يعد بالإمكان استقبال إجابات."
                )
                await interaction.followup.send(msg_closed, ephemeral=True)
                return

            already = await answer_repo.has_answered(self.poll_id, interaction.user.id)
            if already:
                msg_already = (
                    "⚠️ You have already submitted an answer for this challenge."
                    if is_en
                    else "⚠️ لقد قمت بالإجابة على هذا التحدي مسبقاً."
                )
                await interaction.followup.send(msg_already, ephemeral=True)
                return

            question = await question_repo.get_by_id(poll["question_id"])
            if not question:
                msg_missing = (
                    "⚠️ Question data could not be retrieved."
                    if is_en
                    else "⚠️ تعذر العثور على بيانات السؤال."
                )
                await interaction.followup.send(msg_missing, ephemeral=True)
                return

            is_correct = self.choice.upper() == str(question["correct_answer"]).upper()
            inserted = await answer_repo.insert(
                poll_id=self.poll_id,
                user_id=interaction.user.id,
                chosen_answer=self.choice.upper(),
                is_correct=is_correct,
            )

            if not inserted:
                msg_already = (
                    "⚠️ You have already submitted an answer for this challenge."
                    if is_en
                    else "⚠️ لقد قمت بالإجابة على هذا التحدي مسبقاً."
                )
                await interaction.followup.send(msg_already, ephemeral=True)
                return

            # Record streak & milestone rewards in database
            streak_info = await user_repo.record_answer_streak(
                user_id=interaction.user.id,
                poll_id=self.poll_id,
                is_correct=is_correct,
            )

            # Get community vote distribution for anti-bandwagon post-answer display
            dist = await answer_repo.get_choice_distribution(self.poll_id)
            counts = dist.get("counts", {})
            percentages = dist.get("percentages", {})
            total_votes = dist.get("total", 0)

            # Build language-matched ephemeral result embed with streak, explanation, and vote distribution
            color = EMBED_COLOR_CORRECT if is_correct else EMBED_COLOR_WRONG
            current_streak = streak_info.get("current_streak", 0)

            if is_en:
                title = "🎉 Correct Answer! (+10 pts)" if is_correct else "❌ Incorrect Answer (+0 pts)"
                desc = (
                    f"You selected **Option [{self.choice.upper()}]** — Correct!\n"
                    f"Points have been recorded to your leaderboard score."
                    if is_correct
                    else f"You selected **Option [{self.choice.upper()}]** — Incorrect.\n"
                    f"The correct answer is **Option [{question['correct_answer']}]**."
                )
                embed = discord.Embed(title=title, description=desc, color=color)

                streak_line = f"🔥 **Current Streak:** {current_streak} Day{'s' if current_streak != 1 else ''}!"
                if streak_info.get("milestone"):
                    streak_line += f" 🎁 **Milestone Bonus:** `+{streak_info['bonus_points']} pts`!"
                embed.add_field(name="⚡ Streak", value=streak_line, inline=True)

                explanation = str(question.get("explanation_en") or question.get("explanation") or "").strip()
                if explanation:
                    embed.add_field(name="📖 Explanation", value=explanation, inline=False)

                breakdown_text = (
                    f"🇦 **[A]**: {counts.get('A', 0)} ({percentages.get('A', 0)}%)\n"
                    f"🇧 **[B]**: {counts.get('B', 0)} ({percentages.get('B', 0)}%)\n"
                    f"🇨 **[C]**: {counts.get('C', 0)} ({percentages.get('C', 0)}%)\n"
                    f"🇩 **[D]**: {counts.get('D', 0)} ({percentages.get('D', 0)}%)\n"
                    f"👥 **Total Answers:** {total_votes}"
                )
                embed.add_field(name="📊 Community Votes", value=breakdown_text, inline=False)
            else:
                title = "🎉 إجابة صحيحة! (+10 نقاط)" if is_correct else "❌ إجابة خاطئة (+0 نقطة)"
                desc = (
                    f"اخترت **الخيار [{self.choice.upper()}]** — إجابة صحيحة وممتازة!\n"
                    f"أُضيفت النقاط إلى رصيدك وترتيبك في السيرفر."
                    if is_correct
                    else f"اخترت **الخيار [{self.choice.upper()}]** — إجابة غير صحيحة.\n"
                    f"الإجابة الصحيحة هي **الخيار [{question['correct_answer']}]**."
                )
                embed = discord.Embed(title=title, description=desc, color=color)

                streak_line = f"🔥 **السلسلة المتواصلة:** {current_streak} {'يوم' if current_streak == 1 else 'أيام'}!"
                if streak_info.get("milestone"):
                    streak_line += f" 🎁 **مكافأة إنجاز:** `+{streak_info['bonus_points']} نقطة`!"
                embed.add_field(name="⚡ السلسلة", value=streak_line, inline=True)

                explanation = str(question.get("explanation") or question.get("explanation_ar") or question.get("explanation_en") or "").strip()
                if explanation:
                    embed.add_field(name="📖 الشرح والتوضيح", value=explanation, inline=False)

                breakdown_text = (
                    f"🇦 **[A]**: {counts.get('A', 0)} ({percentages.get('A', 0)}%)\n"
                    f"🇧 **[B]**: {counts.get('B', 0)} ({percentages.get('B', 0)}%)\n"
                    f"🇨 **[C]**: {counts.get('C', 0)} ({percentages.get('C', 0)}%)\n"
                    f"🇩 **[D]**: {counts.get('D', 0)} ({percentages.get('D', 0)}%)\n"
                    f"👥 **إجمالي الإجابات:** {total_votes}"
                )
                embed.add_field(name="📊 توزيع تصويت الأعضاء", value=breakdown_text, inline=False)

            # Reply to the user ASAP — before any embed refresh work
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Public Milestone Announcement if 5-day or 10-day streak achieved
            if streak_info.get("milestone"):
                try:
                    ann_channel = interaction.channel or (interaction.client.get_channel(BD_CHANNEL_ID) if BD_CHANNEL_ID else None)
                    if ann_channel:
                        user_avatar = interaction.user.display_avatar.url if interaction.user else None
                        announcement_embed = build_streak_milestone_embed(
                            user_id=interaction.user.id,
                            milestone=streak_info["milestone"],
                            bonus_points=streak_info["bonus_points"],
                            is_en=is_en,
                            user_avatar_url=user_avatar,
                        )
                        await ann_channel.send(
                            content=f"🎉 <@{interaction.user.id}>",
                            embed=announcement_embed,
                        )
                except Exception as e:
                    log.warning(f"ByteDaily: Failed sending streak milestone announcement: {e}")
        except Exception as e:
            log.error(
                f"ByteDaily: Answer callback error poll=#{self.poll_id} "
                f"user={interaction.user.id}: {e}",
                exc_info=True,
            )
            capture_interaction_error(interaction, e, active_poll_id=self.poll_id)
            try:
                await interaction.followup.send(_GENERIC_ANSWER_ERROR, ephemeral=True)
            except Exception:
                pass
            return

        # Best-effort debounced embed refresh (never blocks / fails the user reply)
        try:
            footer_icon = (
                interaction.client.user.display_avatar.url
                if interaction.client.user
                else None
            )
            await schedule_debounced_poll_refresh(
                channel=interaction.channel,
                poll_id=self.poll_id,
                poll=poll,
                question=question,
                footer_icon_url=footer_icon,
                delay=3.0,
            )
        except Exception as e:
            log.warning(
                f"ByteDaily: Could not schedule debounced refresh on poll #{self.poll_id}: {e}"
            )


class DynamicTranslateButton(
    DynamicItem[Button],
    template=r"bd_translate_(?P<poll_id>[0-9]+)",
):
    """Persistent dynamic button for viewing English translation ephemerally."""

    def __init__(
        self,
        poll_id: int,
        disabled: bool = False,
        row: Optional[int] = 1,
    ) -> None:
        super().__init__(
            Button(
                label="🌐 English",
                style=discord.ButtonStyle.secondary,
                custom_id=f"{CUSTOM_ID_PREFIX_TRANSLATE}{poll_id}",
                disabled=disabled,
                row=row,
            )
        )
        self.poll_id = poll_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: Button,
        match: re.Match[str],
        /,
    ) -> "DynamicTranslateButton":
        return cls(poll_id=int(match.group("poll_id")))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _defer_ephemeral(interaction):
            return

        # Automatically save/update user's preferred language to 'en'
        await user_repo.set_preferred_language(interaction.user.id, "en")

        try:
            poll = await poll_repo.get_by_id(self.poll_id)
            if not poll:
                await interaction.followup.send(
                    "⚠️ لم يتم العثور على الاستبيان. | Poll not found.",
                    ephemeral=True,
                )
                return

            question = await question_repo.get_by_id(poll["question_id"])
            if not question:
                await interaction.followup.send(
                    "⚠️ تعذر العثور على بيانات السؤال. | Question data not found.",
                    ephemeral=True,
                )
                return

            # Backward compatibility: handle missing English translation gracefully
            if not question.get("question_en"):
                await interaction.followup.send(
                    "ℹ️ الترجمة الإنجليزية غير متوفرة لهذا التحدي. | English translation is not available for this challenge.",
                    ephemeral=True,
                )
                return

            closes_at = poll_service.resolve_ends_at(poll)
            footer_icon = (
                interaction.client.user.display_avatar.url
                if interaction.client.user
                else None
            )

            embed = build_english_challenge_embed(
                question=question,
                poll_id=self.poll_id,
                closes_at=closes_at,
                footer_icon_url=footer_icon,
            )

            english_view = ByteDailyEnglishAnswerView(poll_id=self.poll_id)
            await interaction.followup.send(embed=embed, view=english_view, ephemeral=True)
        except Exception as e:
            log.error(
                f"ByteDaily: Translate callback error poll=#{self.poll_id} "
                f"user={interaction.user.id}: {e}",
                exc_info=True,
            )
            capture_interaction_error(interaction, e, active_poll_id=self.poll_id)
            try:
                await interaction.followup.send(
                    "⚠️ حدث خطأ في جلب الترجمة، يرجى المحاولة مرة أخرى. | An error occurred while fetching the translation, please try again.",
                    ephemeral=True,
                )
            except Exception:
                pass


class DynamicResultButton(
    DynamicItem[Button],
    template=r"bd_show_result_(?P<poll_id>[0-9]+)",
):
    """Persistent dynamic button for viewing individual user results after poll close."""

    def __init__(self, poll_id: int) -> None:
        super().__init__(
            Button(
                label="📊 نتيجتي | Show My Result",
                style=discord.ButtonStyle.secondary,
                custom_id=f"{CUSTOM_ID_PREFIX_RESULT}{poll_id}",
            )
        )
        self.poll_id = poll_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: Button,
        match: re.Match[str],
        /,
    ) -> "DynamicResultButton":
        return cls(poll_id=int(match.group("poll_id")))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _defer_ephemeral(interaction):
            return

        # Fetch user stats and resolve language preference via 3-tier resolution
        user_stats = await user_repo.get_by_id(interaction.user.id)
        lang = resolve_user_language(interaction, user_stats)
        is_en = lang == "en"

        # Build personal result via followup (never response.send_message)
        try:
            user_answer = await answer_repo.get_user_answer(
                self.poll_id, interaction.user.id
            )
            if not user_answer:
                msg_no_part = (
                    "ℹ️ You did not participate in this challenge."
                    if is_en
                    else "ℹ️ لم تشارك في هذا التحدي."
                )
                await interaction.followup.send(msg_no_part, ephemeral=True)
                return

            poll = await poll_repo.get_by_id(self.poll_id)
            if not poll:
                await interaction.followup.send("⚠️ Poll not found.", ephemeral=True)
                return

            question = await question_repo.get_by_id(poll["question_id"])
            if not question:
                await interaction.followup.send(
                    "⚠️ Question data not found.",
                    ephemeral=True,
                )
                return

            # User stats for streak
            current_streak = int(user_stats.get("current_streak") or 0) if user_stats else 0

            # Fetch vote distribution
            dist = await answer_repo.get_choice_distribution(self.poll_id)
            counts = dist.get("counts", {})
            percentages = dist.get("percentages", {})
            total_votes = dist.get("total", 0)

            is_correct = user_answer.get("is_correct", False)
            color = EMBED_COLOR_CORRECT if is_correct else EMBED_COLOR_WRONG

            if is_en:
                embed = discord.Embed(title="📊 Your Challenge Result", color=color)
                embed.add_field(
                    name="Your Choice",
                    value=f"Option **[{user_answer['chosen_answer']}]**",
                    inline=True,
                )
                embed.add_field(
                    name="Correct Answer",
                    value=f"Option **[{question['correct_answer']}]**",
                    inline=True,
                )
                embed.add_field(
                    name="Outcome",
                    value=(
                        "🎉 **Correct (+10 pts)**"
                        if is_correct
                        else "❌ **Incorrect (+0 pts)**"
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="⚡ Current Streak",
                    value=f"🔥 **{current_streak}** Day{'s' if current_streak != 1 else ''}",
                    inline=True,
                )
                explanation = str(question.get("explanation_en") or question.get("explanation") or "").strip()
                if explanation:
                    embed.add_field(
                        name="📖 Explanation",
                        value=explanation,
                        inline=False,
                    )
                breakdown_text = (
                    f"🇦 **[A]**: {counts.get('A', 0)} ({percentages.get('A', 0)}%)\n"
                    f"🇧 **[B]**: {counts.get('B', 0)} ({percentages.get('B', 0)}%)\n"
                    f"🇨 **[C]**: {counts.get('C', 0)} ({percentages.get('C', 0)}%)\n"
                    f"🇩 **[D]**: {counts.get('D', 0)} ({percentages.get('D', 0)}%)\n"
                    f"👥 **Total Answers:** {total_votes}"
                )
                embed.add_field(name="📊 Community Votes", value=breakdown_text, inline=False)
            else:
                embed = discord.Embed(title="📊 نتيجتك في التحدي", color=color)
                embed.add_field(
                    name="اختيارك",
                    value=f"الخيار **[{user_answer['chosen_answer']}]**",
                    inline=True,
                )
                embed.add_field(
                    name="الإجابة الصحيحة",
                    value=f"الخيار **[{question['correct_answer']}]**",
                    inline=True,
                )
                embed.add_field(
                    name="النتيجة",
                    value=(
                        "🎉 **إجابة صحيحة (+10 نقاط)**"
                        if is_correct
                        else "❌ **إجابة خاطئة (+0 نقطة)**"
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="⚡ السلسلة الحالية",
                    value=f"🔥 **{current_streak}** {'يوم' if current_streak == 1 else 'أيام'}",
                    inline=True,
                )
                explanation = str(question.get("explanation") or question.get("explanation_ar") or question.get("explanation_en") or "").strip()
                if explanation:
                    embed.add_field(
                        name="📖 الشرح والتوضيح",
                        value=explanation,
                        inline=False,
                    )
                breakdown_text = (
                    f"🇦 **[A]**: {counts.get('A', 0)} ({percentages.get('A', 0)}%)\n"
                    f"🇧 **[B]**: {counts.get('B', 0)} ({percentages.get('B', 0)}%)\n"
                    f"🇨 **[C]**: {counts.get('C', 0)} ({percentages.get('C', 0)}%)\n"
                    f"🇩 **[D]**: {counts.get('D', 0)} ({percentages.get('D', 0)}%)\n"
                    f"👥 **إجمالي الإجابات:** {total_votes}"
                )
                embed.add_field(name="📊 توزيع تصويت الأعضاء", value=breakdown_text, inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.error(
                f"ByteDaily: Result callback error poll=#{self.poll_id} "
                f"user={interaction.user.id}: {e}",
                exc_info=True,
            )
            capture_interaction_error(interaction, e, active_poll_id=self.poll_id)
            try:
                await interaction.followup.send(_GENERIC_RESULT_ERROR, ephemeral=True)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# View Containers (Used when sending messages)
# ─────────────────────────────────────────────────────────────────────────────

class ByteDailyAnswerView(View):
    """View container containing the 4 choice buttons + English translation button for a poll."""

    def __init__(self, poll_id: int, disabled: bool = False) -> None:
        super().__init__(timeout=None)
        self.poll_id = poll_id
        for choice in ["A", "B", "C", "D"]:
            self.add_item(
                DynamicAnswerButton(
                    poll_id=poll_id, choice=choice, disabled=disabled, row=0
                )
            )
        self.add_item(
            DynamicTranslateButton(poll_id=poll_id, disabled=disabled, row=1)
        )


class ByteDailyEnglishAnswerView(View):
    """View container containing the 4 choice buttons for answering from the English view."""

    def __init__(self, poll_id: int, disabled: bool = False) -> None:
        super().__init__(timeout=None)
        self.poll_id = poll_id
        for choice in ["A", "B", "C", "D"]:
            self.add_item(
                DynamicAnswerButton(
                    poll_id=poll_id, choice=choice, disabled=disabled, row=0
                )
            )


class ByteDailyResultView(View):
    """View container containing the 'Show My Result' button."""

    def __init__(self, poll_id: int) -> None:
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.add_item(DynamicResultButton(poll_id=poll_id))
