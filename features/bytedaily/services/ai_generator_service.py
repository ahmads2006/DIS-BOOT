"""
ByteDaily AI Generator Service — Automatic question generation using Gemini API.

Sends exactly ONE batch request per day (to respect Free Tier limits)
asking Gemini for a JSON array of `count` medium-difficulty programming questions
in Arabic covering Backend, Laravel/PHP, SQL, Python, JS/TS, Docker, Git, C#.

Parses the returned JSON and inserts questions into `bd_questions` via question_repo.
"""

import json
import os
import re
from typing import Any, Dict, List
import aiohttp

from bridge.legacy_adapter import log
from ..database.repositories import question_repo

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent"

PROMPT_TEMPLATE = """
أنت خبير إعداد أسئلة برمجة وتقنية ومطور برمجيات محترف ثنائي اللغة (العربية والإنجليزية).
قم بإنتاج دفعة من {count} أسئلة خيارات متعددة (MCQ) بمستوى متوسط، باللغتين العربية والإنجليزية بشكل متطابق ودقيق.
التخصصات المستهدفة: (Backend, Laravel/PHP, SQL, Python, JS/TS, Docker, Git, C#).

يجب أن ترجع النتيجة بصيغة JSON Array مصفوفة فقط، بدون أي نصوص أو markdown code blocks أخرى خارج الـ JSON.

كل كائن داخل المصفوفة يجب أن يحتوي بدقة على الحقول التالية:
- "question_ar": نص السؤال باللغة العربية مع توضيح أي كود إن وجد.
- "question_en": نص السؤال باللغة الإنجليزية (English translation of the question).
- "options_ar": كائن يحتوي على خيارات الإجابة بالعربية فقط بالمفاتيح ("A", "B", "C", "D").
- "options_en": كائن يحتوي على خيارات الإجابة بالإنجليزية فقط بالمفاتيح ("A", "B", "C", "D").
- "correct_answer": حرف الخيار الصحيح فقط واحدة من ("A", "B", "C", "D")
- "explanation_ar": شرح موجز ومفيد للجواب الصحيح باللغة العربية.
- "explanation_en": شرح موجز ومفيد للجواب الصحيح باللغة الإنجليزية.
- "category": التخصص (مثال: "Python", "SQL", "Docker", "Laravel", "Git", "Backend").

مثال للصيغة المطلوبة:
[
  {{
    "question_ar": "ما هي الفائدة الرئيسية من استخدام المعامل `yield` في Python؟",
    "question_en": "What is the primary advantage of using the `yield` keyword in Python?",
    "options_ar": {{
      "A": "إنهاء تنفيذ الدالة فوراً",
      "B": "إنشاء دالة مولّدة (Generator) ترجع القيم تدريجياً وتوفر الذاكرة",
      "C": "تسريع تنفيذ العمليات الحسابية",
      "D": "تحويل النص إلى مصفوفة"
    }},
    "options_en": {{
      "A": "Terminate function execution immediately",
      "B": "Create a generator function that produces values lazily and saves memory",
      "C": "Speed up arithmetic operations",
      "D": "Convert string to array"
    }},
    "correct_answer": "B",
    "explanation_ar": "يُستخدم yield لإنشاء Generators والتي تُرجع قيمة واحدة في كل مرة وتستأنف التنفيذ عند الطلب مما يحافظ على الذاكرة.",
    "explanation_en": "yield is used to create generator functions that yield values one at a time on demand, optimizing memory usage.",
    "category": "Python"
  }}
]
"""


from services.ai_service import gemini_circuit_breaker, get_fallback_queued_questions


async def _fetch_gemini_questions(count: int = 5) -> int:
    """
    Send a single API request to Gemini requesting `count` questions in JSON format.
    Parses the response and inserts all valid questions into `bd_questions`.
    Raises exceptions on failures so that the CircuitBreaker can track health.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY", "")
    if not api_key:
        log.warning("ByteDaily AI Generator: GEMINI_API_KEY not found in environment.")
        raise RuntimeError("GEMINI_API_KEY is not configured")

    prompt = PROMPT_TEMPLATE.format(count=count)

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
        }
    }

    url = f"{GEMINI_API_URL}?key={api_key}"

    from core.http_client import get_http_session
    session = await get_http_session()
    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status == 200:
            data = await resp.json()
        elif resp.status in (429, 503):
            text = await resp.text()
            raise RuntimeError(f"Gemini API rate limited/unavailable HTTP {resp.status}: {text}")
        else:
            text = await resp.text()
            raise RuntimeError(f"Gemini API error HTTP {resp.status}: {text}")

    try:
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini payload format: {e}")

    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    questions_list: List[Dict[str, Any]] = json.loads(raw_text)
    if not isinstance(questions_list, list):
        raise ValueError("Gemini response JSON is not a list.")

    inserted_count = 0
    for q in questions_list:
        question_ar = str(q.get("question_ar") or q.get("question_text", "")).strip()
        question_en = str(q.get("question_en", "")).strip() or None

        # Handle options_ar
        options_ar = q.get("options_ar")
        if isinstance(options_ar, dict):
            choice_a = str(options_ar.get("A") or options_ar.get("a", "")).strip()
            choice_b = str(options_ar.get("B") or options_ar.get("b", "")).strip()
            choice_c = str(options_ar.get("C") or options_ar.get("c", "")).strip()
            choice_d = str(options_ar.get("D") or options_ar.get("d", "")).strip()
        else:
            choice_a = str(q.get("choice_a", "")).strip()
            choice_b = str(q.get("choice_b", "")).strip()
            choice_c = str(q.get("choice_c", "")).strip()
            choice_d = str(q.get("choice_d", "")).strip()

        # Handle options_en
        options_en_raw = q.get("options_en")
        options_en = None
        choice_a_en = None
        choice_b_en = None
        choice_c_en = None
        choice_d_en = None

        if isinstance(options_en_raw, dict):
            choice_a_en = str(options_en_raw.get("A") or options_en_raw.get("a", "")).strip() or None
            choice_b_en = str(options_en_raw.get("B") or options_en_raw.get("b", "")).strip() or None
            choice_c_en = str(options_en_raw.get("C") or options_en_raw.get("c", "")).strip() or None
            choice_d_en = str(options_en_raw.get("D") or options_en_raw.get("d", "")).strip() or None
            if choice_a_en or choice_b_en or choice_c_en or choice_d_en:
                options_en = {
                    "A": choice_a_en or "",
                    "B": choice_b_en or "",
                    "C": choice_c_en or "",
                    "D": choice_d_en or "",
                }

        correct_answer = str(q.get("correct_answer", "")).strip().upper()
        explanation_ar = str(q.get("explanation_ar") or q.get("explanation", "")).strip()
        explanation_en = str(q.get("explanation_en", "")).strip() or None
        category = str(q.get("category", "")).strip()

        if not (question_ar and choice_a and choice_b and choice_c and choice_d):
            continue

        if correct_answer not in ("A", "B", "C", "D"):
            continue

        tags = [category] if category else []

        await question_repo.insert(
            question_text=question_ar,
            choice_a=choice_a,
            choice_b=choice_b,
            choice_c=choice_c,
            choice_d=choice_d,
            correct_answer=correct_answer,
            explanation=explanation_ar,
            difficulty=2,  # Medium
            tags=tags,
            question_en=question_en,
            options_en=options_en,
            choice_a_en=choice_a_en,
            choice_b_en=choice_b_en,
            choice_c_en=choice_c_en,
            choice_d_en=choice_d_en,
            explanation_en=explanation_en,
        )
        inserted_count += 1

    if inserted_count == 0:
        raise ValueError("Gemini response contained no valid questions to insert.")

    log.info(f"ByteDaily AI Generator: Successfully generated and inserted {inserted_count} new questions.")
    return inserted_count


async def generate_and_store_questions(count: int = 5) -> int:
    """
    Protected question generation using Circuit Breaker.
    Automatically diverts to pre-generated queued questions in `bd_questions`
    if Gemini is rate-limited, failing, or circuit is OPEN.
    """
    try:
        return await gemini_circuit_breaker.call(
            _fetch_gemini_questions,
            count,
            fallback_func=get_fallback_queued_questions,
        )
    except Exception as e:
        log.error(f"ByteDaily AI Generator: Failed to generate questions via CircuitBreaker: {e}", exc_info=True)
        return 0
