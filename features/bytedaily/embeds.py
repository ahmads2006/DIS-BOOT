"""
ByteDaily Embed Builders — Luxury-themed Discord embeds for challenges.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import discord

from .constants import (
    EMBED_COLOR_QUESTION,
    EMBED_COLOR_STATS,
    EMBED_COLOR_CORRECT,
    EMBED_COLOR_WRONG,
    EMBED_THUMBNAIL_CHALLENGE,
    DIFFICULTY_LABELS,
)


def build_challenge_embed(
    question: Dict[str, Any],
    poll_id: int,
    closes_at: datetime,
    participants: int = 0,
    footer_icon_url: Optional[str] = None,
) -> discord.Embed:
    """
    Build the gold/amber luxury challenge embed.

    Args:
        question: bd_questions row (question_text, choice_a–d, difficulty, …)
        poll_id: Active poll id shown in the title
        closes_at: UTC close time for Discord relative timestamp
        participants: Current answer count
        footer_icon_url: Optional bot avatar for the footer
    """
    difficulty = int(question.get("difficulty") or 1)
    stars, label = DIFFICULTY_LABELS.get(difficulty, DIFFICULTY_LABELS[1])

    if closes_at.tzinfo is None:
        closes_at = closes_at.replace(tzinfo=timezone.utc)
    closes_unix = int(closes_at.timestamp())

    q_text = str(question.get("question_text") or "").strip()
    divider = "`──────────────────────────────`"
    options_block = (
        f"🇦 **[A]** {question.get('choice_a', '')}\n"
        f"{divider}\n"
        f"\u200b\n"
        f"🇧 **[B]** {question.get('choice_b', '')}\n"
        f"{divider}\n"
        f"\u200b\n"
        f"🇨 **[C]** {question.get('choice_c', '')}\n"
        f"{divider}\n"
        f"\u200b\n"
        f"🇩 **[D]** {question.get('choice_d', '')}"
    )
    description = (
        f"> **{q_text}**\n\n"
        f"**الخيارات / Options**\n"
        f"{options_block}"
    )

    embed = discord.Embed(
        title=f"✨ BYTE DAILY | التحدي البرمجي اليومي #{poll_id}",
        description=description,
        color=EMBED_COLOR_QUESTION,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=EMBED_THUMBNAIL_CHALLENGE)

    embed.add_field(
        name="📊 Difficulty / المستوى",
        value=f"{stars} **{label}**",
        inline=True,
    )
    embed.add_field(
        name="⏱️ Closes In / المتبقي",
        value=f"<t:{closes_unix}:R>",
        inline=True,
    )
    embed.add_field(
        name="👥 Participants / المشاركون",
        value=f"**{participants}**",
        inline=True,
    )

    embed.set_footer(
        text="DevQuest Engine • أجب واكسب النقاط لرفع ترتيبك في السيرفر!",
        icon_url=footer_icon_url,
    )
    return embed


def build_results_embed(
    question: Dict[str, Any],
    poll_id: int,
    stats: Dict[str, Any],
    footer_icon_url: Optional[str] = None,
) -> discord.Embed:
    """Build the previous-poll results embed shown in the rolling window."""
    embed = discord.Embed(
        title="📊 BYTE DAILY | نتائج التحدي",
        description=(
            f"أُغلق التصويت على تحدي **#{poll_id}**!\n\n"
            f"**✅ الإجابة الصحيحة:** `{question.get('correct_answer', '?')}`\n\n"
            f"**📖 الشرح:**\n> {question.get('explanation') or '—'}\n\n"
            f"👥 **المشاركون:** {stats.get('total', 0)}\n"
            f"✅ **إجابات صحيحة:** {stats.get('correct', 0)} ({stats.get('percent_correct', 0)}%)\n"
            f"❌ **إجابات خاطئة:** {stats.get('wrong', 0)}"
        ),
        color=EMBED_COLOR_STATS,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(
        text="DevQuest Engine • اضغط الزر لمعرفة نتيجتك الشخصية",
        icon_url=footer_icon_url,
    )
    return embed


_CHOICE_KEYS = {
    "A": "choice_a",
    "B": "choice_b",
    "C": "choice_c",
    "D": "choice_d",
}


def _choice_label(question: Dict[str, Any], letter: str) -> str:
    """Format `A — option text` for a choice letter."""
    key = _CHOICE_KEYS.get(str(letter).upper())
    text = (question.get(key) if key else None) or ""
    letter = str(letter).upper()
    return f"`{letter}` — {text}".strip(" —") if text else f"`{letter}`"


def build_personal_result_dm_embed(
    *,
    poll_id: int,
    question: Dict[str, Any],
    chosen_answer: str,
    is_correct: bool,
    correct_count: int = 0,
    total_questions: int = 1,
    footer_icon_url: Optional[str] = None,
) -> discord.Embed:
    """
    Personal DM report sent after a poll closes.
    Supports a single-question poll today; score fields stay generic for future multi-Q sessions.
    """
    total = max(int(total_questions), 1)
    correct = int(correct_count)
    percent = round((correct / total) * 100) if total else 0
    outcome = "🎉 إجابة صحيحة!" if is_correct else "❌ إجابة خاطئة"
    color = EMBED_COLOR_CORRECT if is_correct else EMBED_COLOR_WRONG

    q_text = str(question.get("question_text") or "").strip()
    explanation = str(question.get("explanation") or "—").strip()
    correct_letter = str(question.get("correct_answer") or "?").upper()
    chosen_letter = str(chosen_answer or "?").upper()

    embed = discord.Embed(
        title=f"📬 تقرير نتيجتك | ByteDaily #{poll_id}",
        description=(
            f"{outcome}\n\n"
            f"**📊 النتيجة النهائية:** `{correct}/{total}` "
            f"({percent}%)"
        ),
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="❓ السؤال",
        value=f"> {q_text}" if q_text else "—",
        inline=False,
    )
    embed.add_field(
        name="📝 إجابتك",
        value=_choice_label(question, chosen_letter),
        inline=True,
    )
    embed.add_field(
        name="✅ الإجابة الصحيحة",
        value=_choice_label(question, correct_letter),
        inline=True,
    )
    embed.add_field(
        name="📖 الشرح",
        value=explanation,
        inline=False,
    )
    embed.set_footer(
        text="DevQuest Engine • أُرسل تلقائياً بعد إغلاق التحدي",
        icon_url=footer_icon_url,
    )
    return embed
