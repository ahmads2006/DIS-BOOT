"""
ByteDaily Views — Discord UI components for the daily question.

Uses discord.ui.DynamicItem for persistent, leak-free button handling:
  1. DynamicAnswerButton: Handles A, B, C, D choices via regex template.
  2. DynamicResultButton: Handles 'Show my result' button via regex template.

Views:
  - ByteDailyAnswerView: Container for the 4 dynamic answer buttons when sending.
  - ByteDailyResultView: Container for the dynamic result button when sending.

Callbacks ALWAYS defer within the first milliseconds so Discord never shows
"The application didn't respond in time", then reply via followup.send().
"""

import re
from typing import Optional
import discord
from discord.ui import Button, DynamicItem, View

from bridge.legacy_adapter import log
from .constants import (
    CUSTOM_ID_PREFIX_ANSWER,
    CUSTOM_ID_PREFIX_RESULT,
    CHOICE_EMOJIS,
    EMBED_COLOR_CORRECT,
    EMBED_COLOR_WRONG,
)
from .database.repositories import answer_repo, poll_repo, question_repo
from .services import poll_service
from .embeds import build_challenge_embed


_GENERIC_ANSWER_ERROR = "⚠️ حدث خطأ في معالجة الإجابة، يرجى المحاولة مرة أخرى."
_GENERIC_RESULT_ERROR = "⚠️ حدث خطأ في جلب النتيجة، يرجى المحاولة مرة أخرى."


async def _safe_defer(interaction: discord.Interaction) -> bool:
    """
    Acknowledge the interaction immediately (must finish within ~3s).
    Returns True if deferred (or already acknowledged), False on hard failure.
    """
    try:
        if interaction.response.is_done():
            return True
        await interaction.response.defer(ephemeral=True)
        return True
    except discord.NotFound:
        # Interaction token expired / unknown — nothing we can do
        log.warning("ByteDaily: Interaction expired before defer.")
        return False
    except discord.HTTPException as e:
        log.warning(f"ByteDaily: Failed to defer interaction: {e}")
        return False


async def _safe_followup(
    interaction: discord.Interaction,
    content: Optional[str] = None,
    *,
    embed: Optional[discord.Embed] = None,
) -> None:
    """Send an ephemeral followup; never raise to the caller."""
    try:
        kwargs = {"ephemeral": True}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        await interaction.followup.send(**kwargs)
    except Exception as e:
        log.warning(f"ByteDaily: followup.send failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Buttons (Registered ONCE globally on bot startup)
# ─────────────────────────────────────────────────────────────────────────────

class DynamicAnswerButton(
    DynamicItem[Button],
    template=r"bd_answer_(?P<poll_id>[0-9]+)_(?P<choice>[A-D])",
):
    """Persistent dynamic button for answering A, B, C, or D."""

    def __init__(self, poll_id: int, choice: str, disabled: bool = False) -> None:
        # Put the regional-indicator in the label only — using both emoji= and
        # label= renders as "A A" in Discord for 🇦/🇧/🇨/🇩.
        emoji = CHOICE_EMOJIS.get(choice.upper(), choice)
        super().__init__(
            Button(
                label=f"{emoji} {choice}",
                style=discord.ButtonStyle.primary,
                custom_id=f"{CUSTOM_ID_PREFIX_ANSWER}{poll_id}_{choice}",
                disabled=disabled,
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
        # 1) Acknowledge Discord IMMEDIATELY (prevents 3s timeout)
        if not await _safe_defer(interaction):
            return

        # 2) Process answer + respond via followup
        try:
            poll = await poll_repo.get_by_id(self.poll_id)
            if not poll or poll.get("status") != "open":
                await _safe_followup(
                    interaction,
                    "⚠️ This challenge is already closed. Answers are no longer accepted.",
                )
                return

            already = await answer_repo.has_answered(self.poll_id, interaction.user.id)
            if already:
                await _safe_followup(
                    interaction,
                    "⚠️ You have already submitted an answer for this challenge.",
                )
                return

            question = await question_repo.get_by_id(poll["question_id"])
            if not question:
                await _safe_followup(
                    interaction,
                    "⚠️ Question data could not be retrieved.",
                )
                return

            is_correct = self.choice.upper() == str(question["correct_answer"]).upper()
            inserted = await answer_repo.insert(
                poll_id=self.poll_id,
                user_id=interaction.user.id,
                chosen_answer=self.choice.upper(),
                is_correct=is_correct,
            )

            if not inserted:
                await _safe_followup(
                    interaction,
                    "⚠️ You have already submitted an answer for this challenge.",
                )
                return

            # Reply to the user ASAP — before any embed refresh work
            await _safe_followup(
                interaction,
                f"✅ You selected **{self.choice}**! Your answer is recorded.\n"
                "Results will be revealed when voting closes.",
            )
        except Exception as e:
            log.error(
                f"ByteDaily: Answer callback error poll=#{self.poll_id} "
                f"user={interaction.user.id}: {e}",
                exc_info=True,
            )
            await _safe_followup(interaction, _GENERIC_ANSWER_ERROR)
            return

        # 3) Best-effort embed refresh (never blocks / fails the user reply)
        try:
            counts = await answer_repo.count_for_poll(self.poll_id)
            closes_at = poll_service.resolve_ends_at(poll)
            footer_icon = (
                interaction.client.user.display_avatar.url
                if interaction.client.user
                else None
            )
            embed = build_challenge_embed(
                question=question,
                poll_id=self.poll_id,
                closes_at=closes_at,
                participants=counts.get("total", 0),
                footer_icon_url=footer_icon,
            )
            message_id = poll.get("message_id")
            channel = interaction.channel
            if channel and message_id:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed)
        except Exception as e:
            log.warning(
                f"ByteDaily: Could not refresh participant count on poll #{self.poll_id}: {e}"
            )


class DynamicResultButton(
    DynamicItem[Button],
    template=r"bd_show_result_(?P<poll_id>[0-9]+)",
):
    """Persistent dynamic button for viewing individual user results after poll close."""

    def __init__(self, poll_id: int) -> None:
        super().__init__(
            Button(
                label="📊 Show My Result",
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
        # 1) Acknowledge Discord IMMEDIATELY
        if not await _safe_defer(interaction):
            return

        # 2) Build personal result via followup
        try:
            user_answer = await answer_repo.get_user_answer(
                self.poll_id, interaction.user.id
            )
            if not user_answer:
                await _safe_followup(
                    interaction,
                    "ℹ️ You did not participate in this challenge.",
                )
                return

            poll = await poll_repo.get_by_id(self.poll_id)
            if not poll:
                await _safe_followup(interaction, "⚠️ Poll not found.")
                return

            question = await question_repo.get_by_id(poll["question_id"])
            if not question:
                await _safe_followup(interaction, "⚠️ Question data not found.")
                return

            is_correct = user_answer.get("is_correct", False)
            color = EMBED_COLOR_CORRECT if is_correct else EMBED_COLOR_WRONG

            embed = discord.Embed(title="📊 Your Challenge Result", color=color)
            embed.add_field(
                name="Your Choice",
                value=f"Option **{user_answer['chosen_answer']}**",
                inline=True,
            )
            embed.add_field(
                name="Correct Answer",
                value=f"Option **{question['correct_answer']}**",
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
            if question.get("explanation"):
                embed.add_field(
                    name="Explanation",
                    value=question["explanation"],
                    inline=False,
                )

            await _safe_followup(interaction, embed=embed)
        except Exception as e:
            log.error(
                f"ByteDaily: Result callback error poll=#{self.poll_id} "
                f"user={interaction.user.id}: {e}",
                exc_info=True,
            )
            await _safe_followup(interaction, _GENERIC_RESULT_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# View Containers (Used when sending messages)
# ─────────────────────────────────────────────────────────────────────────────

class ByteDailyAnswerView(View):
    """View container containing the 4 choice buttons for a poll."""

    def __init__(self, poll_id: int, disabled: bool = False) -> None:
        super().__init__(timeout=None)
        self.poll_id = poll_id
        for choice in ["A", "B", "C", "D"]:
            self.add_item(
                DynamicAnswerButton(poll_id=poll_id, choice=choice, disabled=disabled)
            )


class ByteDailyResultView(View):
    """View container containing the 'Show My Result' button."""

    def __init__(self, poll_id: int) -> None:
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.add_item(DynamicResultButton(poll_id=poll_id))
