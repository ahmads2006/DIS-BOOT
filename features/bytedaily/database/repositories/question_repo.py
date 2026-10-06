"""
ByteDaily Question Repository — Data access for bd_questions table.

All queries run against the bd_db singleton pool.
Pure SQL via asyncpg — no ORM. Returns plain dicts.
"""

import json
from typing import Any, Dict, List, Optional, Union
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
    question_en: Optional[str] = None,
    options_en: Optional[Union[Dict[str, str], str]] = None,
    choice_a_en: Optional[str] = None,
    choice_b_en: Optional[str] = None,
    choice_c_en: Optional[str] = None,
    choice_d_en: Optional[str] = None,
    explanation_en: Optional[str] = None,
) -> int:
    """
    Insert a new question with optional English translations.
    Returns the new question ID.
    """
    options_en_json = (
        json.dumps(options_en)
        if isinstance(options_en, dict)
        else (options_en if isinstance(options_en, str) else None)
    )

    if isinstance(options_en, dict):
        choice_a_en = choice_a_en or options_en.get("A") or options_en.get("a")
        choice_b_en = choice_b_en or options_en.get("B") or options_en.get("b")
        choice_c_en = choice_c_en or options_en.get("C") or options_en.get("c")
        choice_d_en = choice_d_en or options_en.get("D") or options_en.get("d")

    try:
        return await bd_db.fetchval(
            """
            INSERT INTO bd_questions
                (question_text, choice_a, choice_b, choice_c, choice_d,
                 correct_answer, explanation, difficulty, tags,
                 question_en, options_en, choice_a_en, choice_b_en, choice_c_en, choice_d_en, explanation_en)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13, $14, $15, $16)
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
            question_en,
            options_en_json,
            choice_a_en,
            choice_b_en,
            choice_c_en,
            choice_d_en,
            explanation_en,
        )
    except Exception as e:
        # Fallback to legacy insert if columns don't exist yet on unmigrated db
        if "question_en" in str(e) or "column" in str(e).lower():
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
        raise


async def deactivate(question_id: int) -> bool:
    """Set is_active=FALSE. Returns True if a row was updated."""
    result = await bd_db.execute(
        "UPDATE bd_questions SET is_active = FALSE WHERE id = $1",
        question_id,
    )
    return result.split()[-1] != '0'
