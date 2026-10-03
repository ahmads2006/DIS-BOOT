"""
ByteDaily Question Repository — Data access for bd_questions table.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.
"""

from typing import Any, Dict, List, Optional
from ..client import bd_db


async def get_active_questions(exclude_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """
    Return all questions where is_active=TRUE.
    If exclude_ids is provided (non-empty), excludes those question IDs.
    """
    if exclude_ids:
        query = "SELECT * FROM bd_questions WHERE is_active = TRUE AND id != ALL($1::bigint[])"
        return await bd_db.fetch(query, exclude_ids)
    return await bd_db.fetch("SELECT * FROM bd_questions WHERE is_active = TRUE")


async def get_random_question(
    exclude_ids: Optional[List[int]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pick one random active question, optionally excluding IDs already asked.
    Uses ORDER BY RANDOM() LIMIT 1 for DB-side selection (avoids loading all rows).
    Returns None if no matching active question exists.
    """
    if exclude_ids:
        return await bd_db.fetchrow(
            """
            SELECT * FROM bd_questions
            WHERE is_active = TRUE
              AND id != ALL($1::bigint[])
            ORDER BY RANDOM()
            LIMIT 1
            """,
            exclude_ids,
        )
    return await bd_db.fetchrow(
        """
        SELECT * FROM bd_questions
        WHERE is_active = TRUE
        ORDER BY RANDOM()
        LIMIT 1
        """
    )


async def get_by_id(question_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single question row by ID. Returns None if not found."""
    return await bd_db.fetchrow(
        "SELECT * FROM bd_questions WHERE id = $1",
        question_id,
    )


async def insert(
    question_text: str,
    choice_a: str,
    choice_b: str,
    choice_c: str,
    choice_d: str,
    correct_answer: str,
    explanation: str = '',
    difficulty: int = 1,
    tags: Optional[List[str]] = None,
) -> int:
    """Insert a new question. Returns the new question ID."""
    return await bd_db.fetchval(
        """
        INSERT INTO bd_questions
            (question_text, choice_a, choice_b, choice_c, choice_d,
             correct_answer, explanation, difficulty, tags)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id
        """,
        question_text,
        choice_a,
        choice_b,
        choice_c,
        choice_d,
        correct_answer,
        explanation,
        difficulty,
        tags or [],
    )


async def deactivate(question_id: int) -> bool:
    """Set is_active=FALSE. Returns True if a row was updated."""
    result = await bd_db.execute(
        "UPDATE bd_questions SET is_active = FALSE WHERE id = $1",
        question_id,
    )
    return result.split()[-1] != '0'
