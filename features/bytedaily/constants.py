"""
ByteDaily Constants — All magic numbers, timing values, and identifiers.

Centralizes configuration so nothing is hardcoded in business logic.
Values that should come from .env are loaded here via config.py.
All other features/bytedaily/ modules import from here — never hardcode.
"""

# TODO: Import discord
# TODO: Import os (to read BD_CHANNEL_ID from env)
# TODO: from config import ... if any ByteDaily settings are added to config.py

# ── Timing ──────────────────────────────────────────────────────────────────
# TODO: ANSWER_WINDOW_SECONDS: int = 6 * 60 * 60    # 6 hours — members have this long to answer
# TODO: CLEANUP_DELAY_SECONDS: int = 4 * 60 * 60    # 4 hours after close — then delete + repost

# ── Scoring ──────────────────────────────────────────────────────────────────
# TODO: POINTS_CORRECT: int = 10     # points awarded for a correct answer
# TODO: POINTS_WRONG: int = 0        # points for a wrong answer (none in MVP)

# ── Channel ──────────────────────────────────────────────────────────────────
# TODO: BD_CHANNEL_ID: int | None = int(os.getenv("BD_CHANNEL_ID", "0")) or None
#       (None = not configured; scheduler must guard against this)

# ── Embed colours ────────────────────────────────────────────────────────────
# TODO: EMBED_COLOR_QUESTION = discord.Color.blurple()     # question post embed
# TODO: EMBED_COLOR_STATS    = discord.Color.og_blurple()  # stats summary embed
# TODO: EMBED_COLOR_CORRECT  = discord.Color.green()       # result: correct
# TODO: EMBED_COLOR_WRONG    = discord.Color.red()         # result: wrong

# ── Persistent view custom_id prefixes ──────────────────────────────────────
# Pattern: f"{PREFIX}{poll_id}_{choice}"  or  f"{PREFIX}{poll_id}"
# TODO: CUSTOM_ID_PREFIX_ANSWER: str = "bd_answer_"
# TODO: CUSTOM_ID_PREFIX_RESULT: str = "bd_show_result_"

# ── Question selection ───────────────────────────────────────────────────────
# TODO: RECENT_QUESTION_LOOKBACK: int = 30  # avoid repeating last N questions
