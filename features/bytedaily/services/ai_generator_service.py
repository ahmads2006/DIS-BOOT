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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent"

PROMPT_TEMPLATE = """
أنت خبير إعداد أسئلة برمجة وتقنية باللغة العربية.
قم بإنتاج دفعة من {count} أسئلة خيارات متعددة (MCQ) بمستوى متوسط، باللغة العربية.
التخصصات المستهدفة: (Backend, Laravel/PHP, SQL, Python, JS/TS, Docker, Git, C#).

يجب أن ترجع النتيجة بصيغة JSON Array مصفوفة فقط، بدون أي نصوص أخرى خارج الـ JSON.

كل كائن داخل المصفوفة يجب أن يحتوي على الحقول التالية:
- "question_text": نص السؤال باللغة العربية مع توضيح أي كود إن وجد.
- "choice_a": الخيار A
- "choice_b": الخيار B
- "choice_c": الخيار C
- "choice_d": الخيار D
- "correct_answer": حرف الخيار الصحيح فقط واحدة من ("A", "B", "C", "D")
- "explanation": شرح موجز ومفيد للجواب الصحيح باللغة العربية.
- "category": التخصص (مثال: "Python", "SQL", "Docker", "Laravel", "Git").

مثال للصيغة المطلوبة:
[
  {{
    "question_text": "ما هي الفائدة الرئيسية من استخدام المعامل `yield` في Python؟",
    "choice_a": "إنهاء تنفيذ الدالة فوراً",
    "choice_b": "إنشاء دالة مولّدة (Generator) ترجع القيم تدريجياً وتوفر الذاكرة",
    "choice_c": "تسريع تنفيذ العمليات الحسابية",
    "choice_d": "تحويل النص إلى مصفوفة",
    "correct_answer": "B",
    "explanation": "يُستخدم yield لإنشاء Generators والتي تُرجع قيمة واحدة في كل مرة وتستأنف التنفيذ عند الطلب مما يحافظ على الذاكرة.",
    "category": "Python"
  }}
]
"""


async def generate_and_store_questions(count: int = 5) -> int:
    """
    Send a single API request to Gemini requesting `count` questions in JSON format.
    Parses the response and inserts all valid questions into `bd_questions`.
    Returns the number of successfully inserted questions.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY") or GEMINI_API_KEY
    if not api_key:
        log.warning("ByteDaily AI Generator: GEMINI_API_KEY not found in environment. Skipping AI generation.")
        return 0

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

    try:
        import asyncio as _asyncio
        async with aiohttp.ClientSession() as session:
            data = None
            for attempt in range(1, 3):  # max 2 attempts
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        break
                    elif resp.status == 503 and attempt < 2:
                        log.warning(
                            f"ByteDaily AI Generator: Gemini API returned 503 (overloaded), "
                            f"retrying in 5s (attempt {attempt}/2)..."
                        )
                        await _asyncio.sleep(5)
                    else:
                        text = await resp.text()
                        log.error(f"ByteDaily AI Generator: Gemini API error HTTP {resp.status}: {text}")
                        return 0

            if data is None:
                log.error("ByteDaily AI Generator: All retry attempts failed.")
                return 0

        try:
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError) as e:
            log.error(f"ByteDaily AI Generator: Unexpected Gemini payload format: {e}")
            return 0

        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)

        questions_list: List[Dict[str, Any]] = json.loads(raw_text)
        if not isinstance(questions_list, list):
            log.error("ByteDaily AI Generator: Gemini response JSON is not a list.")
            return 0

        inserted_count = 0
        for q in questions_list:
            question_text = str(q.get("question_text", "")).strip()
            choice_a = str(q.get("choice_a", "")).strip()
            choice_b = str(q.get("choice_b", "")).strip()
            choice_c = str(q.get("choice_c", "")).strip()
            choice_d = str(q.get("choice_d", "")).strip()
            correct_answer = str(q.get("correct_answer", "")).strip().upper()
            explanation = str(q.get("explanation", "")).strip()
            category = str(q.get("category", "")).strip()

            if not (question_text and choice_a and choice_b and choice_c and choice_d):
                continue

            if correct_answer not in ("A", "B", "C", "D"):
                continue

            tags = [category] if category else []

            await question_repo.insert(
                question_text=question_text,
                choice_a=choice_a,
                choice_b=choice_b,
                choice_c=choice_c,
                choice_d=choice_d,
                correct_answer=correct_answer,
                explanation=explanation,
                difficulty=2,  # Medium
                tags=tags,
            )
            inserted_count += 1

        log.info(f"ByteDaily AI Generator: Successfully generated and inserted {inserted_count} new questions.")
        return inserted_count

    except Exception as e:
        log.error(f"ByteDaily AI Generator: Exception during AI question generation: {e}", exc_info=True)
        return 0
