"""
Gemini AI Circuit Breaker & Resilient Question Generation Service.

Features:
  - Three-state Circuit Breaker (CLOSED, OPEN, HALF-OPEN).
  - Trips to OPEN on 3 consecutive failures or immediate RateLimit / Quota (429, 503) errors.
  - Automatically holds OPEN for 10 minutes (600s) before probe testing in HALF-OPEN.
  - Automatic fallback to queued / pre-generated questions in bd_questions without blocking the scheduler.
  - Contextual Sentry alerts and structured structlog metrics.
"""

import asyncio
import enum
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from core.logging import log, measure_duration
from core.sentry import capture_exception


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is attempted while the circuit is OPEN."""
    def __init__(self, message: str, retry_after: float):
        super().__init__(message)
        self.retry_after = retry_after


class CircuitBreaker:
    """
    Asynchronous Circuit Breaker pattern implementation.
    """

    def __init__(
        self,
        name: str = "gemini_api",
        failure_threshold: int = 3,
        recovery_timeout: float = 600.0,  # 10 minutes
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: float = 0.0
        self.last_state_change: float = time.time()
        self._lock = asyncio.Lock()

    def get_status(self) -> Dict[str, Any]:
        """Return operational metrics for monitoring."""
        now = time.time()
        time_until_retry = max(0.0, self.recovery_timeout - (now - self.last_failure_time))
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout,
            "seconds_until_probe": round(time_until_retry, 1) if self.state == CircuitState.OPEN else 0,
        }

    async def can_execute(self) -> bool:
        """Evaluate if an outgoing request is allowed through."""
        async with self._lock:
            now = time.time()
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                if (now - self.last_failure_time) >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                    log.info(
                        f"Circuit breaker '{self.name}': Recovery timeout expired. Transitioning to HALF-OPEN for probe test.",
                        state="HALF_OPEN",
                    )
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                # Allow probe test
                return True

            return False

    async def record_success(self) -> None:
        """Record successful invocation and reset circuit."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                log.info(
                    f"Circuit breaker '{self.name}': Probe test succeeded. Resetting circuit to CLOSED.",
                    state="CLOSED",
                )
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_state_change = time.time()

    async def record_failure(self, error: Optional[BaseException] = None) -> None:
        """Record failed invocation, count failures, or trip immediately on quota limit."""
        async with self._lock:
            now = time.time()
            self.last_failure_time = now
            self.failure_count += 1

            error_str = str(error) if error else ""
            is_quota_or_rate_limit = (
                "429" in error_str
                or "503" in error_str
                or "ResourceExhausted" in error_str
                or "QuotaExceeded" in error_str
                or "rate_limit" in error_str.lower()
            )

            # Trip to OPEN immediately on quota/rate limits OR if threshold is reached
            if is_quota_or_rate_limit or self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.last_state_change = now
                log.warning(
                    f"🚨 Circuit breaker '{self.name}' TRIPPED to OPEN state for {int(self.recovery_timeout)}s (10 min)!",
                    consecutive_failures=self.failure_count,
                    reason="quota_rate_limit" if is_quota_or_rate_limit else "failure_threshold_exceeded",
                    error=error_str[:120],
                )
                capture_exception(
                    RuntimeError(f"CircuitBreaker '{self.name}' tripped to OPEN: {error_str}"),
                    tags={"circuit_breaker": self.name, "state": "OPEN"},
                )
            else:
                log.warning(
                    f"Circuit breaker '{self.name}' failure recorded ({self.failure_count}/{self.failure_threshold})",
                    error=error_str[:120],
                )

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        fallback_func: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an async callable protected by the circuit breaker.
        Automatically falls back if circuit is OPEN or callable fails.
        """
        if not await self.can_execute():
            time_left = max(1.0, self.recovery_timeout - (time.time() - self.last_failure_time))
            log.warning(
                f"Circuit breaker '{self.name}' is OPEN. Diverting to fallback immediately.",
                seconds_remaining=round(time_left, 1),
            )
            if fallback_func:
                return await fallback_func(*args, **kwargs)
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. Retrying allowed in {int(time_left)}s.",
                retry_after=time_left,
            )

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure(e)
            if fallback_func:
                log.info(f"Invoking resilient fallback for '{self.name}' after failure...")
                return await fallback_func(*args, **kwargs)
            raise


# Global Singleton for Gemini API Circuit Breaker
gemini_circuit_breaker = CircuitBreaker(
    name="gemini_api",
    failure_threshold=3,
    recovery_timeout=600.0,  # 10 minutes
)


# ─────────────────────────────────────────────────────────────────────────────
# Resilient Fallback Question Provider
# ─────────────────────────────────────────────────────────────────────────────

async def get_fallback_queued_questions(count: int = 5) -> int:
    """
    Fallback mechanism when Gemini AI is unavailable or rate-limited:
    Verifies that bd_questions has available unasked or backup questions,
    ensuring the daily cycle continues smoothly without stalling.
    """
    from features.bytedaily.database.repositories import question_repo

    log.info(f"Fallback Question Provider: Fetching {count} queued questions from bank...")
    active_questions = await question_repo.get_active_questions()
    if active_questions:
        log.info(
            f"Fallback Question Provider: Successfully verified {len(active_questions)} existing questions ready in bank."
        )
        return min(count, len(active_questions))

    log.warning("Fallback Question Provider: No unused questions in DB. Using verified static fallback seed.")
    # Safe seeded fallback if bank is totally empty
    seed_count = 0
    try:
        sample_questions = [
            {
                "question_text": "ما هي الدالة المستخدمة لتحويل نص إلى مصفوفة بايتات في Python؟",
                "choice_a": "str.encode()",
                "choice_b": "bytes.decode()",
                "choice_c": "str.to_bytes()",
                "choice_d": "format()",
                "correct_answer": "A",
                "explanation": "الدالة encode() تقوم بترميز السلسلة النصية إلى بايتات (bytes) باستخدام UTF-8 بشكل افتراضي.",
                "question_en": "Which method is used to encode a string into bytes in Python?",
                "choice_a_en": "str.encode()",
                "choice_b_en": "bytes.decode()",
                "choice_c_en": "str.to_bytes()",
                "choice_d_en": "format()",
                "explanation_en": "The encode() method encodes the string into bytes using UTF-8 by default.",
                "tags": ["Python", "Backend"],
            },
            {
                "question_text": "ما هو دور الأمر `EXPLAIN ANALYZE` في قواعد بيانات PostgreSQL؟",
                "choice_a": "إنشاء فهرس جديد تلقائياً",
                "choice_b": "تنفيذ الاستعلام وعرض خطة التنفيذ الفعلية مع التكلفة والوقت",
                "choice_c": "حذف البيانات المكررة",
                "choice_d": "تغيير إعدادات السيرفر",
                "correct_answer": "B",
                "explanation": "يقوم EXPLAIN ANALYZE بتشغيل الاستعلام وعرض خطة التنفيذ مع إحصائيات الوقت الفعلي.",
                "question_en": "What is the purpose of `EXPLAIN ANALYZE` in PostgreSQL?",
                "choice_a_en": "Automatically create a new index",
                "choice_b_en": "Execute the query and show the execution plan with actual runtime and cost",
                "choice_c_en": "Delete duplicate rows",
                "choice_d_en": "Change server configuration",
                "explanation_en": "EXPLAIN ANALYZE runs the query and displays the actual execution plan with execution time.",
                "tags": ["SQL", "Databases"],
            },
        ]

        for q in sample_questions:
            await question_repo.insert(
                question_text=q["question_text"],
                choice_a=q["choice_a"],
                choice_b=q["choice_b"],
                choice_c=q["choice_c"],
                choice_d=q["choice_d"],
                correct_answer=q["correct_answer"],
                explanation=q["explanation"],
                difficulty=1,
                tags=q["tags"],
                question_en=q["question_en"],
                choice_a_en=q["choice_a_en"],
                choice_b_en=q["choice_b_en"],
                choice_c_en=q["choice_c_en"],
                choice_d_en=q["choice_d_en"],
                explanation_en=q["explanation_en"],
            )
            seed_count += 1
    except Exception as e:
        log.error("Failed to seed fallback questions", error=str(e))

    return seed_count
