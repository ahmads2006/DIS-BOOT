"""
ByteDaily User Repository — Data access for bd_users table + RPC.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.

The bd_upsert_user_stats RPC function handles the atomic upsert + streak
logic inside PostgreSQL — this repository simply calls it.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from bridge.legacy_adapter import log
from ..client import bd_db

_PREF_LANG_CACHE: Dict[int, Tuple[Optional[str], float]] = {}
_USER_ROW_CACHE: Dict[int, Tuple[Optional[Dict[str, Any]], float]] = {}
_CACHE_TTL_SECONDS = 60.0


def invalidate_user_cache(user_id: Optional[int] = None) -> None:
    """Invalidate cache for a specific user or all users."""
    if user_id is not None:
        _PREF_LANG_CACHE.pop(user_id, None)
        _USER_ROW_CACHE.pop(user_id, None)
    else:
        _PREF_LANG_CACHE.clear()
        _USER_ROW_CACHE.clear()


async def upsert_stats(
    user_id: int,
    is_correct: bool,
    points: int,
    poll_id: int,
) -> None:
    """
    Call streak/stats updater for a user after poll close or answer submission.
    Idempotent: skips if the poll was already recorded for this user.
    """
    row = await get_by_id(user_id)
    if row and (row.get("last_answered_poll_id") == poll_id or row.get("last_poll_id") == poll_id):
        return

    await record_answer_streak(user_id=user_id, poll_id=poll_id, is_correct=is_correct)


async def record_answer_streak(
    user_id: int,
    poll_id: int,
    is_correct: bool,
) -> Dict[str, Any]:
    """
    Process answer streak and milestone rewards for a user:
      - Correct:
          - If last_answered_poll_id == poll_id - 1 -> current_streak += 1
          - Else -> current_streak = 1
          - highest_streak = max(highest_streak, current_streak)
          - Milestones:
              - 5-Day Streak: +10 bonus points
              - 10-Day Streak: +30 bonus points
      - Incorrect:
          - current_streak = 0
    Returns dict: {'current_streak': int, 'highest_streak': int, 'bonus_points': int, 'milestone': Optional[int]}
    """
    user_row = await get_by_id(user_id)
    if user_row:
        last_poll = user_row.get("last_answered_poll_id") or user_row.get("last_poll_id")
        current_streak = int(user_row.get("current_streak") or 0)
        highest_streak = int(user_row.get("highest_streak") or user_row.get("best_streak") or 0)
    else:
        last_poll = None
        current_streak = 0
        highest_streak = 0

    if is_correct:
        if last_poll is not None and last_poll == (poll_id - 1):
            new_streak = current_streak + 1
        else:
            new_streak = 1
        new_highest = max(highest_streak, new_streak)

        # Milestone bonuses
        if new_streak == 5:
            bonus_points = 10
            milestone = 5
        elif new_streak == 10:
            bonus_points = 30
            milestone = 10
        else:
            bonus_points = 0
            milestone = None

        points_to_add = 10 + bonus_points
        correct_inc = 1
        wrong_inc = 0
    else:
        new_streak = 0
        new_highest = highest_streak
        bonus_points = 0
        milestone = None
        points_to_add = 0
        correct_inc = 0
        wrong_inc = 1

    try:
        await bd_db.execute(
            """
            INSERT INTO bd_users (
                user_id,
                total_points,
                correct_count,
                wrong_count,
                current_streak,
                highest_streak,
                best_streak,
                last_answered_poll_id,
                last_poll_id,
                updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $6, $7, $7, now()
            )
            ON CONFLICT (user_id)
            DO UPDATE SET
                total_points = bd_users.total_points + $2,
                correct_count = bd_users.correct_count + $3,
                wrong_count = bd_users.wrong_count + $4,
                current_streak = $5,
                highest_streak = GREATEST(bd_users.highest_streak, $6),
                best_streak = GREATEST(bd_users.best_streak, $6),
                last_answered_poll_id = $7,
                last_poll_id = $7,
                updated_at = now()
            """,
            user_id,
            points_to_add,
            correct_inc,
            wrong_inc,
            new_streak,
            new_highest,
            poll_id,
        )
    except Exception as e:
        # Fallback to legacy column layout if migration 008 is not yet applied
        log.warning(f"ByteDaily: Standard streak insert fallback: {e}")
        try:
            await bd_db.execute(
                """
                INSERT INTO bd_users (
                    user_id, total_points, correct_count, wrong_count, current_streak, best_streak, last_poll_id, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, now())
                ON CONFLICT (user_id)
                DO UPDATE SET
                    total_points = bd_users.total_points + $2,
                    correct_count = bd_users.correct_count + $3,
                    wrong_count = bd_users.wrong_count + $4,
                    current_streak = $5,
                    best_streak = GREATEST(bd_users.best_streak, $6),
                    last_poll_id = $7,
                    updated_at = now()
                """,
                user_id,
                points_to_add,
                correct_inc,
                wrong_inc,
                new_streak,
                new_highest,
                poll_id,
            )
        except Exception as inner_e:
            log.error(f"ByteDaily: Failed to record answer streak for user {user_id}: {inner_e}")

    invalidate_user_cache(user_id)
    log.info(
        f"ByteDaily: User {user_id} answer recorded for poll #{poll_id} "
        f"(correct={is_correct}, streak={new_streak}, highest={new_highest}, "
        f"bonus={bonus_points}, milestone={milestone})."
    )

    return {
        "current_streak": new_streak,
        "highest_streak": new_highest,
        "bonus_points": bonus_points,
        "milestone": milestone,
    }


async def get_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single user's stats row with short in-memory TTL caching."""
    now = time.time()
    if user_id in _USER_ROW_CACHE:
        val, ts = _USER_ROW_CACHE[user_id]
        if (now - ts) < _CACHE_TTL_SECONDS:
            return val

    row = await bd_db.fetchrow(
        "SELECT * FROM bd_users WHERE user_id = $1",
        user_id,
    )
    _USER_ROW_CACHE[user_id] = (row, now)
    return row


async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return the top `limit` users by total_points, with 1-based rank.
    Each dict includes: user_id, total_points, correct_count, wrong_count,
                         current_streak, best_streak, rank.
    """
    return await bd_db.fetch(
        """
        SELECT *,
            RANK() OVER (ORDER BY total_points DESC) AS rank
        FROM bd_users
        ORDER BY total_points DESC
        LIMIT $1
        """,
        limit,
    )


async def get_rank(user_id: int) -> Optional[int]:
    """
    Return the 1-based rank of a user by total_points.
    Returns None if the user is not in bd_users.
    """
    exists = await bd_db.fetchval(
        "SELECT total_points FROM bd_users WHERE user_id = $1",
        user_id,
    )
    if exists is None:
        return None

    rank = await bd_db.fetchval(
        """
        SELECT COUNT(*) + 1 FROM bd_users
        WHERE total_points > (
            SELECT total_points FROM bd_users WHERE user_id = $1
        )
        """,
        user_id,
    )
    return int(rank) if rank is not None else None


async def get_total_users() -> int:
    """Return the total number of users who have participated in ByteDaily."""
    count = await bd_db.fetchval("SELECT COUNT(*) FROM bd_users")
    return int(count) if count is not None else 0


async def reset_leaderboard_points() -> int:
    """
    Zero out total_points and streaks for all users (leaderboard reset).
    Leaves correct/wrong answer counts intact.
    Returns the number of rows updated.
    """
    invalidate_user_cache(None)
    result = await bd_db.execute(
        """
        UPDATE bd_users
        SET total_points = 0,
            current_streak = 0,
            best_streak = 0,
            updated_at = NOW()
        """
    )
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0


async def get_preferred_language(user_id: int) -> Optional[str]:
    """
    Get the user's explicit preferred language ('ar' or 'en') with TTL caching.
    Returns None if the user has not explicitly set a language preference,
    allowing automatic role-based language resolution.
    """
    now = time.time()
    if user_id in _PREF_LANG_CACHE:
        val, ts = _PREF_LANG_CACHE[user_id]
        if (now - ts) < _CACHE_TTL_SECONDS:
            return val

    try:
        lang = await bd_db.fetchval(
            "SELECT preferred_language FROM bd_users WHERE user_id = $1",
            user_id,
        )
        res = str(lang).lower() if lang and str(lang).lower() in ("ar", "en") else None
        _PREF_LANG_CACHE[user_id] = (res, now)
        return res
    except Exception:
        return None


async def set_preferred_language(user_id: int, language: Optional[str] = "en") -> None:
    """
    Set or update the user's preferred language ('ar', 'en', or None/auto).
    Upserts into bd_users so preferences are saved even before first answer.
    """
    lang = language.lower() if language and language.lower() in ("ar", "en") else None
    try:
        await bd_db.execute(
            """
            INSERT INTO bd_users (user_id, preferred_language, updated_at)
            VALUES ($1, $2, now())
            ON CONFLICT (user_id)
            DO UPDATE SET preferred_language = EXCLUDED.preferred_language, updated_at = now()
            """,
            user_id,
            lang,
        )
        _PREF_LANG_CACHE[user_id] = (lang, time.time())
        _USER_ROW_CACHE.pop(user_id, None)
        log.info(f"ByteDaily: Set preferred_language='{lang}' for user {user_id}.")
    except Exception as e:
        log.warning(f"ByteDaily: Could not set preferred_language for user {user_id}: {e}")


async def get_user_detailed_stats(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch comprehensive developer profile statistics for a user, including:
    - User stats row from bd_users (points, streaks, counts)
    - 1-based leaderboard rank
    - Total participants count
    - Answer accuracy percentage
    - Top tags/categories answered correctly
    - Unlocked badges list
    """
    stats = await get_by_id(user_id)
    if not stats:
        return None

    rank = await get_rank(user_id)
    total_users = await get_total_users()

    correct = int(stats.get("correct_count", 0))
    wrong = int(stats.get("wrong_count", 0))
    total_ans = correct + wrong
    accuracy = round((correct / total_ans) * 100) if total_ans > 0 else 0
    points = int(stats.get("total_points", 0))
    current_streak = int(stats.get("current_streak", 0))
    best_streak = int(stats.get("best_streak", 0) or stats.get("highest_streak", 0))

    # Calculate unlocked badges
    badges = []
    if points >= 10:
        badges.append(("🎯", "First Step", "الخطوة الأولى"))
    if points >= 50:
        badges.append(("⚡", "Fast Learner", "متعلم نشط"))
    if points >= 100:
        badges.append(("🚀", "Century Club", "نادي المئة نقطة"))
    if points >= 250:
        badges.append(("💎", "Master Coder", "خبير الأكواد"))
    if points >= 500:
        badges.append(("👑", "Legendary Dev", "مطور أسطوري"))

    if best_streak >= 3:
        badges.append(("🔥", "On Fire", "شعلة الحماس (3 أيام)"))
    if best_streak >= 5:
        badges.append(("🌟", "Unstoppable", "لا يتوقف (5 أيام)"))
    if best_streak >= 10:
        badges.append(("🏆", "Streak Legend", "أسطورة الـ Streak (10 أيام)"))

    if rank == 1:
        badges.append(("🥇", "#1 Champion", "بطل السيرفر الأول"))
    elif rank in (2, 3):
        badges.append(("🥈", "Top 3 Elite", "نخبة التوب 3"))
    elif rank and rank <= 10:
        badges.append(("🏅", "Top 10 Contender", "من أفضل 10 مطورين"))

    # Top category query if available
    top_categories = []
    try:
        cat_rows = await bd_db.fetch(
            """
            SELECT unnest(q.tags) AS tag, COUNT(*) AS count
            FROM bd_answers a
            JOIN bd_polls p ON a.poll_id = p.id
            JOIN bd_questions q ON p.question_id = q.id
            WHERE a.user_id = $1 AND a.is_correct = TRUE AND q.tags IS NOT NULL
            GROUP BY tag
            ORDER BY count DESC
            LIMIT 3
            """,
            user_id,
        )
        top_categories = [r["tag"] for r in cat_rows if r.get("tag")]
    except Exception:
        top_categories = []

    return {
        "user_id": user_id,
        "total_points": points,
        "correct_count": correct,
        "wrong_count": wrong,
        "total_answers": total_ans,
        "accuracy": accuracy,
        "current_streak": current_streak,
        "best_streak": best_streak,
        "rank": rank,
        "total_users": total_users,
        "badges": badges,
        "top_categories": top_categories,
        "preferred_language": stats.get("preferred_language"),
        "reminder_enabled": bool(stats.get("reminder_enabled", False)),
    }


async def get_reminder_status(user_id: int) -> bool:
    """Check if the user has enabled daily streak reminders."""
    row = await get_by_id(user_id)
    if not row:
        return False
    return bool(row.get("reminder_enabled", False))


async def toggle_reminder(user_id: int) -> bool:
    """
    Toggle daily streak reminder setting for user.
    Returns the new boolean status (True = enabled, False = disabled).
    """
    current = await get_reminder_status(user_id)
    new_status = not current
    try:
        await bd_db.execute(
            """
            INSERT INTO bd_users (user_id, reminder_enabled, updated_at)
            VALUES ($1, $2, now())
            ON CONFLICT (user_id)
            DO UPDATE SET reminder_enabled = EXCLUDED.reminder_enabled, updated_at = now()
            """,
            user_id,
            new_status,
        )
        invalidate_user_cache(user_id)
        log.info(f"ByteDaily: Set reminder_enabled={new_status} for user {user_id}.")
        return new_status
    except Exception as e:
        log.error(f"ByteDaily: Failed to toggle reminder for user {user_id}: {e}", exc_info=True)
        return current


async def get_unanswered_reminder_subscribers(poll_id: int) -> List[int]:
    """
    Get user IDs who subscribed to reminders and have NOT submitted an answer for poll_id yet.
    """
    try:
        rows = await bd_db.fetch(
            """
            SELECT u.user_id
            FROM bd_users u
            WHERE u.reminder_enabled IS TRUE
              AND u.user_id NOT IN (
                  SELECT a.user_id FROM bd_answers a WHERE a.poll_id = $1
              )
            """,
            poll_id,
        )
        return [r["user_id"] for r in rows if r.get("user_id")]
    except Exception as e:
        log.error(f"ByteDaily: Error fetching unanswered reminder subscribers for poll #{poll_id}: {e}", exc_info=True)
        return []




