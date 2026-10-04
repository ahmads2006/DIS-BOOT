"""
ByteDaily Embed Builders — Luxury-themed Discord embeds for challenges.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import discord

from .constants import (
    EMBED_COLOR_QUESTION,
    EMBED_COLOR_STATS,
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
    description = (
        f"> **{q_text}**\n\n"
        f"**الخيارات / Options**\n"
        f"🇦  `{question.get('choice_a', '')}`\n"
        f"🇧  `{question.get('choice_b', '')}`\n"
        f"🇨  `{question.get('choice_c', '')}`\n"
        f"🇩  `{question.get('choice_d', '')}`"
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
