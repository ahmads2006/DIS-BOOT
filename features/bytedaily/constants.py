"""
ByteDaily Constants — All magic numbers, timing values, and identifiers.

Centralizes configuration so nothing is hardcoded in business logic.
Values that should come from .env are loaded here via os.getenv.
All other features/bytedaily/ modules import from here — never hardcode.
"""

import os
from typing import Optional
import discord

# ── Timing ──────────────────────────────────────────────────────────────────
POST_HOUR_UTC: int = 12                      # 12:00 PM UTC daily post hour
ANSWER_WINDOW_SECONDS: int = 12 * 60 * 60     # 12 hours — members have this long to answer
CLEANUP_DELAY_SECONDS: int = 12 * 60 * 60     # 12 hours after close — then delete + next question

# ── Scoring ──────────────────────────────────────────────────────────────────
POINTS_CORRECT: int = 10      # points awarded for a correct answer
POINTS_WRONG: int = 0         # points for a wrong answer (none in MVP)

# ── Channel ──────────────────────────────────────────────────────────────────
_raw_channel_id = os.getenv("BD_CHANNEL_ID", "0")
BD_CHANNEL_ID: Optional[int] = int(_raw_channel_id) if _raw_channel_id.isdigit() and int(_raw_channel_id) != 0 else None

_raw_lb_channel_id = os.getenv("BD_LEADERBOARD_CHANNEL_ID", "0")
BD_LEADERBOARD_CHANNEL_ID: Optional[int] = int(_raw_lb_channel_id) if _raw_lb_channel_id.isdigit() and int(_raw_lb_channel_id) != 0 else None

# ── Embed colours ────────────────────────────────────────────────────────────
EMBED_COLOR_QUESTION = discord.Color(0xF59E0B)     # gold/amber — challenge post
EMBED_COLOR_LEADERBOARD = discord.Color(0x8B5CF6)  # royal purple — live leaderboard
EMBED_COLOR_STATS    = discord.Color(0xF59E0B)     # gold accent — results summary
EMBED_COLOR_CORRECT  = discord.Color.green()       # result: correct
EMBED_COLOR_WRONG    = discord.Color.red()         # result: wrong

# ── Embed media ──────────────────────────────────────────────────────────────
EMBED_THUMBNAIL_CHALLENGE: str = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
EMBED_THUMBNAIL_LEADERBOARD: str = "https://cdn-icons-png.flaticon.com/512/3176/3176298.png"

# difficulty (1–3) → (star bar, bilingual label)
DIFFICULTY_LABELS = {
    1: ("⭐", "Beginner"),
    2: ("⭐⭐", "Intermediate"),
    3: ("⭐⭐⭐", "Advanced"),
}

# Answer button regional-indicator emojis
CHOICE_EMOJIS = {
    "A": "🇦",
    "B": "🇧",
    "C": "🇨",
    "D": "🇩",
}

# ── Persistent view custom_id prefixes ──────────────────────────────────────
# Pattern: f"{CUSTOM_ID_PREFIX_ANSWER}{poll_id}_{choice}" or f"{CUSTOM_ID_PREFIX_RESULT}{poll_id}"
CUSTOM_ID_PREFIX_ANSWER: str = "bd_answer_"
CUSTOM_ID_PREFIX_RESULT: str = "bd_show_result_"

# ── Question selection ───────────────────────────────────────────────────────
RECENT_QUESTION_LOOKBACK: int = 30  # avoid repeating last N questions
