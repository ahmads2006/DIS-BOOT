"""
ByteDaily Embed Builders — Luxury-themed Discord embeds for challenges.
"""

import json
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


def build_english_challenge_embed(
    question: Dict[str, Any],
    poll_id: int,
    closes_at: datetime,
    footer_icon_url: Optional[str] = None,
) -> discord.Embed:
    """
    Build the English translation embed (ephemeral view).

    Args:
        question: bd_questions row (question_en, options_en, tags, difficulty, ...)
        poll_id: Active poll id shown in the title
        closes_at: UTC close time for Discord relative timestamp
        footer_icon_url: Optional bot avatar for the footer
    """
    difficulty = int(question.get("difficulty") or 1)
    stars, label = DIFFICULTY_LABELS.get(difficulty, DIFFICULTY_LABELS[1])

    if closes_at.tzinfo is None:
        closes_at = closes_at.replace(tzinfo=timezone.utc)
    closes_unix = int(closes_at.timestamp())

    q_text_en = str(question.get("question_en") or "").strip()

    # Extract English options
    opts = question.get("options_en")
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except Exception:
            opts = {}
    if not isinstance(opts, dict):
        opts = {}

    opt_a = opts.get("A") or opts.get("a") or question.get("choice_a_en") or question.get("choice_a") or ""
    opt_b = opts.get("B") or opts.get("b") or question.get("choice_b_en") or question.get("choice_b") or ""
    opt_c = opts.get("C") or opts.get("c") or question.get("choice_c_en") or question.get("choice_c") or ""
    opt_d = opts.get("D") or opts.get("d") or question.get("choice_d_en") or question.get("choice_d") or ""

    divider = "`──────────────────────────────`"
    options_block = (
        f"🇦 **[A]** {opt_a}\n"
        f"{divider}\n"
        f"\u200b\n"
        f"🇧 **[B]** {opt_b}\n"
        f"{divider}\n"
        f"\u200b\n"
        f"🇨 **[C]** {opt_c}\n"
        f"{divider}\n"
        f"\u200b\n"
        f"🇩 **[D]** {opt_d}"
    )
    description = (
        f"> **{q_text_en}**\n\n"
        f"**Options**\n"
        f"{options_block}"
    )

    embed = discord.Embed(
        title=f"🌐 BYTE DAILY | Daily Challenge #{poll_id} (English)",
        description=description,
        color=EMBED_COLOR_QUESTION,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=EMBED_THUMBNAIL_CHALLENGE)

    embed.add_field(
        name="📊 Difficulty",
        value=f"{stars} **{label}**",
        inline=True,
    )

    tags = question.get("tags") or []
    category = tags[0] if tags and len(tags) > 0 else "General Tech"
    embed.add_field(
        name="🏷️ Category",
        value=f"**{category}**",
        inline=True,
    )

    embed.add_field(
        name="⏱️ Closes In",
        value=f"<t:{closes_unix}:R>",
        inline=True,
    )

    embed.set_footer(
        text="DevQuest Engine • Select your answer on the main challenge message!",
        icon_url=footer_icon_url,
    )
    return embed


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
        text="DevQuest Engine • أجب واكسب النقاط لرفع ترتيبك في السيرفر! | Answer & earn points to rank up!",
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
        title="📊 BYTE DAILY | نتائج التحدي • Challenge Results",
        description=(
            f"أُغلق التصويت على تحدي **#{poll_id}**! • Voting closed for Challenge **#{poll_id}**!\n\n"
            f"**✅ الإجابة الصحيحة / Correct Answer:** `{question.get('correct_answer', '?')}`\n\n"
            f"**📖 الشرح / Explanation:**\n> {question.get('explanation') or '—'}\n\n"
            f"👥 **المشاركون / Participants:** {stats.get('total', 0)}\n"
            f"✅ **إجابات صحيحة / Correct:** {stats.get('correct', 0)} ({stats.get('percent_correct', 0)}%)\n"
            f"❌ **إجابات خاطئة / Incorrect:** {stats.get('wrong', 0)}"
        ),
        color=EMBED_COLOR_STATS,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(
        text="DevQuest Engine • اضغط الزر لمعرفة نتيجتك الشخصية | Click button below for personal result",
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
    outcome = "🎉 إجابة صحيحة! / Correct Answer! (+10 pts)" if is_correct else "❌ إجابة خاطئة / Incorrect Answer (+0 pts)"
    color = EMBED_COLOR_CORRECT if is_correct else EMBED_COLOR_WRONG

    q_text = str(question.get("question_text") or "").strip()
    explanation = str(question.get("explanation") or "—").strip()
    correct_letter = str(question.get("correct_answer") or "?").upper()
    chosen_letter = str(chosen_answer or "?").upper()

    embed = discord.Embed(
        title=f"📬 تقرير نتيجتك | ByteDaily #{poll_id} Result Report",
        description=(
            f"{outcome}\n\n"
            f"**📊 النتيجة النهائية / Final Score:** `{correct}/{total}` "
            f"({percent}%)"
        ),
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="❓ السؤال / Question",
        value=f"> {q_text}" if q_text else "—",
        inline=False,
    )
    embed.add_field(
        name="📝 إجابتك / Your Answer",
        value=_choice_label(question, chosen_letter),
        inline=True,
    )
    embed.add_field(
        name="✅ الإجابة الصحيحة / Correct Answer",
        value=_choice_label(question, correct_letter),
        inline=True,
    )
    embed.add_field(
        name="📖 الشرح / Explanation",
        value=explanation,
        inline=False,
    )
    embed.set_footer(
        text="DevQuest Engine • أُرسل تلقائياً بعد إغلاق التحدي | Sent automatically after challenge close",
        icon_url=footer_icon_url,
    )
    return embed


def build_streak_milestone_embed(
    user_id: int,
    milestone: int,
    bonus_points: int,
    is_en: bool = False,
    user_avatar_url: Optional[str] = None,
) -> discord.Embed:
    """
    Build public celebratory announcement embed for streak milestones (5 days, 10 days).
    """
    if milestone == 10:
        color = discord.Color(0xFFD700)  # Gold border for epic 10-day streak
        if is_en:
            title = "🏆 EPIC ACHIEVEMENT! 10-Day Streak Milestone"
            desc = (
                f"👑 **Unstoppable Mastery & Consistency!** 👑\n\n"
                f"⚡ Outstanding congratulations to <@{user_id}> for achieving an epic **10-day streak** of correct answers in ByteDaily!\n\n"
                f"🎁 **Reward:** `+{bonus_points} Bonus Points` awarded to your total leaderboard score!\n"
                f"🌟 Keep up the phenomenal consistency and problem-solving mastery!"
            )
        else:
            title = "🏆 إنجاز أسطوري! سلسلة 10 أيام متواصلة"
            desc = (
                f"👑 **إتقان وإصرار لا يتوقف!** 👑\n\n"
                f"⚡ مبارك للمبرمج <@{user_id}> تحقيق **سلسلة 10 أيام متواصلة** من الإجابات الصحيحة في ByteDaily!\n\n"
                f"🎁 **المكافأة:** `+{bonus_points} نقطة إضافية` أُضيفت إلى رصيدك وترتيبك في لوحة المتصدرين!\n"
                f"🌟 استمر في هذا الأداء المبهر والمتميز!"
            )
    else:  # 5-day milestone
        color = discord.Color(0xF59E0B)  # Amber / Flame
        if is_en:
            title = "🔥 NEW MILESTONE! 5-Day Streak"
            desc = (
                f"🎉 Great job <@{user_id}> for reaching a **5-day streak** of correct answers in ByteDaily!\n\n"
                f"🎁 **Reward:** `+{bonus_points} Bonus Points` awarded to your total leaderboard score!\n"
                f"💪 Keep going strong towards the 10-day milestone!"
            )
        else:
            title = "🔥 إنجاز جديد! سلسلة 5 أيام متواصلة"
            desc = (
                f"🎉 تهانينا للمبرمج <@{user_id}> على تحقيق **سلسلة 5 أيام متواصلة** من الإجابات الصحيحة في ByteDaily!\n\n"
                f"🎁 **المكافأة:** `+{bonus_points} نقاط إضافية` أُضيفت إلى رصيدك وترتيبك في السيرفر!\n"
                f"💪 واصل التقدم نحو التحديات القادمة!"
            )

    embed = discord.Embed(
        title=title,
        description=desc,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    if user_avatar_url:
        embed.set_thumbnail(url=user_avatar_url)
    embed.set_footer(text="DevQuest Engine • ByteDaily Gamification")
    return embed

