import time
from typing import Dict, List, Optional, Any
from core.logger import log
from config import DATABASE_URL

try:
    import asyncpg
except ImportError:
    asyncpg = None

class DatabaseLayer:
    """
    طبقة وسيطة متصلة مباشرة بقاعدة بيانات Supabase (PostgreSQL) عبر asyncpg.
    تتضمن نظام Fallback تلقائي للذاكرة في حال انقطاع الاتصال.
    """
    def __init__(self):
        self.database_url = DATABASE_URL
        self.pool: Optional[Any] = None
        self.is_connected = False

        # ذاكرة احتياطية محلية
        self._local_cooldowns: Dict[int, Dict[str, float]] = {}
        self._local_exam_history: List[Dict[str, Any]] = []

    async def initialize(self):
        if not self.database_url or not asyncpg:
            log.info("ℹ️ DATABASE_URL not provided or asyncpg missing. Running in In-Memory mode.")
            return

        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=5,
                timeout=10,
                command_timeout=10,
                statement_cache_size=0
            )
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            self.is_connected = True
            log.info("✅ Connected to Supabase PostgreSQL database successfully!")
        except Exception as e:
            self.is_connected = False
            log.warning(f"⚠️ Could not connect to Supabase PostgreSQL: {e}. Running in In-Memory mode.")

    async def close(self):
        if self.pool:
            await self.pool.close()
            log.info("Database connection pool closed.")

    # ==========================
    # إدارة فترات الانتظار (Cooldowns)
    # ==========================

    async def get_cooldown_remaining(self, user_id: int, role: str) -> Optional[int]:
        now = time.time()

        if self.is_connected and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT expires_at FROM cooldowns WHERE user_id = $1 AND role = $2",
                        user_id, role
                    )
                    if row:
                        expires_at = float(row["expires_at"])
                        if now >= expires_at:
                            await self.reset_cooldown(user_id, role)
                            return None
                        return int(expires_at - now)
                    return None
            except Exception as e:
                log.error(f"PostgreSQL error getting cooldown: {e}")

        # Fallback
        user_cds = self._local_cooldowns.get(user_id)
        if not user_cds or role not in user_cds:
            return None
        expiry = user_cds[role]
        if now >= expiry:
            del user_cds[role]
            return None
        return int(expiry - now)

    async def set_cooldown(self, user_id: int, role: str, duration_seconds: int):
        expiry = time.time() + duration_seconds

        if self.is_connected and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO cooldowns (user_id, role, expires_at)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, role)
                        DO UPDATE SET expires_at = EXCLUDED.expires_at
                        """,
                        user_id, role, expiry
                    )
                    log.info(f"Saved cooldown to Supabase: user={user_id}, role={role}, expires_in={duration_seconds}s")
                    return
            except Exception as e:
                log.error(f"PostgreSQL error setting cooldown: {e}")

        # Fallback
        if user_id not in self._local_cooldowns:
            self._local_cooldowns[user_id] = {}
        self._local_cooldowns[user_id][role] = expiry

    async def reset_cooldown(self, user_id: int, role: Optional[str] = None) -> bool:
        if self.is_connected and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    if role:
                        result = await conn.execute(
                            "DELETE FROM cooldowns WHERE user_id = $1 AND role = $2",
                            user_id, role
                        )
                    else:
                        result = await conn.execute(
                            "DELETE FROM cooldowns WHERE user_id = $1",
                            user_id
                        )
                    deleted = result.split()[-1] if result else "0"
                    log.info(f"Deleted cooldown from Supabase for user {user_id} (Rows: {deleted})")
                    return int(deleted) > 0
            except Exception as e:
                log.error(f"PostgreSQL error resetting cooldown: {e}")

        # Fallback
        if user_id in self._local_cooldowns:
            if role:
                if role in self._local_cooldowns[user_id]:
                    del self._local_cooldowns[user_id][role]
                    return True
            else:
                del self._local_cooldowns[user_id]
                return True
        return False

    # ==========================
    # سجل الاختبارات والإحصائيات
    # ==========================

    async def record_exam_attempt(self, user_id: int, role: str, score: int, passed: bool):
        now = time.time()

        if self.is_connected and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO exam_history (user_id, role, score, passed, timestamp)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        user_id, role, score, passed, now
                    )
                    log.info(f"Recorded exam to Supabase: user={user_id}, role={role}, passed={passed}")
                    return
            except Exception as e:
                log.error(f"PostgreSQL error recording exam: {e}")

        # Fallback
        self._local_exam_history.append({
            "user_id": user_id,
            "role": role,
            "score": score,
            "passed": passed,
            "timestamp": now,
        })

    async def get_user_history(self, user_id: int) -> List[Dict[str, Any]]:
        if self.is_connected and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT user_id, role, score, passed, timestamp
                        FROM exam_history
                        WHERE user_id = $1
                        ORDER BY id DESC
                        LIMIT 10
                        """,
                        user_id
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                log.error(f"PostgreSQL error fetching user history: {e}")

        return [r for r in self._local_exam_history if r["user_id"] == user_id]

    async def get_stats(self) -> Dict[str, Any]:
        all_records = []

        if self.is_connected and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT role, passed, score FROM exam_history"
                    )
                    all_records = [dict(r) for r in rows]
            except Exception as e:
                log.error(f"PostgreSQL error fetching stats: {e}")

        if not all_records:
            all_records = self._local_exam_history

        total_attempts = len(all_records)
        passed_attempts = sum(1 for r in all_records if r.get("passed", False))
        failed_attempts = total_attempts - passed_attempts

        role_counts: Dict[str, int] = {}
        for r in all_records:
            role = r.get("role", "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1

        return {
            "total_attempts": total_attempts,
            "passed": passed_attempts,
            "failed": failed_attempts,
            "success_rate": round((passed_attempts / total_attempts * 100), 1) if total_attempts > 0 else 0,
            "popular_roles": sorted(role_counts.items(), key=lambda x: x[1], reverse=True),
        }

db = DatabaseLayer()
