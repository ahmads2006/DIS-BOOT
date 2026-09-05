import time
import asyncio
import discord
from typing import Tuple, Optional, Any
from config import (
    ROLE_MAP,
    PUBLIC_LOG_CHANNEL_NAME,
    COOLDOWN_SECONDS,
    QUESTIONS_COUNT,
    QUESTION_TIMEOUT_SECONDS,
    ONBOARDING_COPY
)
from core.state import active_exams
from core.database import db
from core.logger import log
from DATA import get_random_questions

async def start_exam_core(bot: discord.Client, user: discord.User, guild_id: int, role_key: str, lang: str = "ar") -> Tuple[str, Any]:
    """
    بدء اختبار جديد للمستخدم.
    ترجع Tuple مثل ("ok", dm_channel) أو ("cooldown", hours) أو ("already_active",) إلخ.
    """
    if user.id in active_exams:
        return ("already_active",)

    # التحقق من فترة الانتظار (Cooldown)
    cooldown_rem = await db.get_cooldown_remaining(user.id, role_key)
    if cooldown_rem is not None:
        remaining_hours = max(1, int(cooldown_rem / 3600))
        return ("cooldown", remaining_hours)

    # جلب الأسئلة
    questions = get_random_questions(role_key, count=QUESTIONS_COUNT)
    if not questions:
        log.warning(f"No questions found for role '{role_key}'")
        return ("no_questions",)

    # فتح رسائل الخاص للمستخدم
    try:
        dm = await user.create_dm()
    except discord.Forbidden:
        log.warning(f"DMs are closed for user {user.name} ({user.id})")
        return ("dm_forbidden",)

    # حفظ حالة الاختبار (مع قائمة لتتبع رسائل DM لحذفها لاحقاً)
    active_exams[user.id] = {
        "role": role_key,
        "guild_id": guild_id,
        "index": 0,
        "selected_questions": questions,
        "score": 0,
        "start_time": time.time(),
        "lang": lang,
        "current_message_id": None,
        "dm_message_ids": [],  # تتبع كل رسائل الاختبار في DM لحذفها بعد الانتهاء
    }

    log.info(f"Exam started: user={user.name} ({user.id}), role={role_key}")
    return ("ok", dm)


async def send_next_question(bot: discord.Client, user: discord.User, dm_channel: discord.DMChannel):
    """
    إرسال السؤال التالي للمستخدم مع أزرار الخيارات.
    """
    exam = active_exams.get(user.id)
    if not exam:
        return

    from views.exam_views import QuestionView

    current_idx = exam["index"]
    total = len(exam["selected_questions"])
    q_data = exam["selected_questions"][current_idx]

    embed = discord.Embed(
        title=f"📝 السؤال {current_idx + 1} من {total}",
        description=f"**{q_data['q']}**",
        color=discord.Color.blue()
    )

    choices_text = "\n".join([f"**{k}** : {v}" for k, v in q_data["c"].items()])
    embed.add_field(name="الخيارات:", value=choices_text, inline=False)
    embed.set_footer(text=f"⏰ الوقت المتاح: {QUESTION_TIMEOUT_SECONDS} ثانية")

    view = QuestionView(bot=bot, user=user, timeout_seconds=QUESTION_TIMEOUT_SECONDS)
    msg = await dm_channel.send(embed=embed, view=view)
    exam["current_message_id"] = msg.id
    exam["dm_message_ids"].append(msg.id)  # تتبع الرسالة


async def process_answer(bot: discord.Client, user: discord.User, chosen_choice: str, interaction: discord.Interaction):
    """
    معالجة إجابة المستخدم والتنقل للسؤال التالي أو إنهاء الاختبار.
    """
    exam = active_exams.get(user.id)
    if not exam:
        await interaction.response.send_message("❌ انتهت جلسة الاختبار أو تم إلغاؤها.", ephemeral=True)
        return

    current_idx = exam["index"]
    q_data = exam["selected_questions"][current_idx]
    correct_choice = q_data.get("a", "").strip().upper()

    if chosen_choice.upper() == correct_choice:
        exam["score"] += 1

    exam["index"] += 1

    # هل هناك أسئلة متبقية؟
    if exam["index"] < len(exam["selected_questions"]):
        await send_next_question(bot, user, user.dm_channel or await user.create_dm())
    else:
        # انتهت كل الأسئلة - تقييم النتيجة
        total = len(exam["selected_questions"])
        passed = (exam["score"] == total)
        role_key = exam["role"]
        lang = exam.get("lang", "ar")

        if passed:
            await handle_exam_success(bot, user, exam)
        else:
            await handle_exam_fail(bot, user, exam)


async def _cleanup_dm_messages(user: discord.User, message_ids: list):
    """
    حذف جميع رسائل الاختبار من DM بعد فترة قصيرة.
    ينتظر 30 ثانية ليقرأ المستخدم النتيجة ثم يحذف كل شيء.
    """
    try:
        await asyncio.sleep(30)  # ينتظر 30 ثانية ليقرأ المستخدم النتيجة
        dm = await user.create_dm()
        for msg_id in message_ids:
            try:
                msg = await dm.fetch_message(msg_id)
                await msg.delete()
                await asyncio.sleep(0.5)  # تجنب rate limit
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        log.info(f"Cleaned up {len(message_ids)} exam DM messages for {user.name}")
    except Exception as e:
        log.warning(f"Error cleaning up DM messages for {user.name}: {e}")


async def handle_exam_success(bot: discord.Client, user: discord.User, exam: dict):
    """
    منح الرتبة، إرسال إشعار في القناة العامة، وتوثيق النجاح.
    """
    role_key = exam["role"]
    guild_id = exam["guild_id"]
    lang = exam.get("lang", "ar")
    copy = ONBOARDING_COPY.get(lang, ONBOARDING_COPY["ar"])
    dm_message_ids = list(exam.get("dm_message_ids", []))

    role_name = ROLE_MAP.get(role_key, role_key)
    guild = bot.get_guild(guild_id)

    role_assigned = False
    if guild:
        member = guild.get_member(user.id)
        role_obj = discord.utils.get(guild.roles, name=role_name)

        if member and role_obj:
            # التحقق من هرمية الرتب (Bot Role Hierarchy Safety)
            bot_member = guild.get_member(bot.user.id)
            if bot_member and bot_member.top_role > role_obj:
                try:
                    await member.add_roles(role_obj)
                    role_assigned = True
                    log.info(f"Role '{role_name}' granted to {user.name}")
                except Exception as e:
                    log.error(f"Failed to add role '{role_name}' to {user.name}: {e}")
            else:
                log.warning(f"Bot role is lower than target role '{role_name}' in guild {guild.name}")

        # إشعار في قناة الإعلانات
        log_channel = discord.utils.get(guild.text_channels, name=PUBLIC_LOG_CHANNEL_NAME)
        if log_channel:
            try:
                announcement = discord.Embed(
                    title="🎉 مبروك! إنجاز جديد في السيرفر",
                    description=f"تهانينا لـ {user.mention}! لقد اجتاز الاختبار التقني بنجاح وأصبح الآن **{role_name}** 🚀",
                    color=discord.Color.green()
                )
                await log_channel.send(embed=announcement)
            except Exception as e:
                log.error(f"Error sending log to {PUBLIC_LOG_CHANNEL_NAME}: {e}")

    # إشعار المستخدم في الخاص
    result_msg = None
    try:
        success_embed = discord.Embed(
            title="🎉 نتيجة الاختبار: اجتياز كامل!",
            description=f"{copy['success_dm']}\n\n**الرتبة الممنوحة:** {role_name}\n**الدرجة:** {exam['score']}/{len(exam['selected_questions'])}",
            color=discord.Color.green()
        )
        success_embed.set_footer(text="⏳ سيتم حذف هذه المحادثة تلقائياً خلال 30 ثانية...")
        result_msg = await user.send(embed=success_embed)
    except Exception as e:
        log.warning(f"Could not send success DM to {user.name}: {e}")

    # التوثيق والحذف من الذاكرة
    await db.record_exam_attempt(user.id, role_key, exam["score"], passed=True)
    active_exams.pop(user.id, None)

    # حذف رسائل الاختبار من DM بعد 30 ثانية
    if result_msg:
        dm_message_ids.append(result_msg.id)
    asyncio.create_task(_cleanup_dm_messages(user, dm_message_ids))


async def handle_exam_fail(bot: discord.Client, user: discord.User, exam: dict):
    """
    تطبيق فترة الانتظار، إرسال رسالة توضيحية، وتوثيق المحاولة.
    """
    role_key = exam["role"]
    lang = exam.get("lang", "ar")
    copy = ONBOARDING_COPY.get(lang, ONBOARDING_COPY["ar"])
    role_name = ROLE_MAP.get(role_key, role_key)
    dm_message_ids = list(exam.get("dm_message_ids", []))

    await db.set_cooldown(user.id, role_key, COOLDOWN_SECONDS)
    await db.record_exam_attempt(user.id, role_key, exam["score"], passed=False)

    result_msg = None
    try:
        fail_embed = discord.Embed(
            title="📊 نتيجة الاختبار",
            description=f"**النتيجة:** {exam['score']}/{len(exam['selected_questions'])}\n\n{copy['fail_dm']}",
            color=discord.Color.red()
        )
        fail_embed.set_footer(text="⏳ سيتم حذف هذه المحادثة تلقائياً خلال 30 ثانية...")
        result_msg = await user.send(embed=fail_embed)
    except Exception as e:
        log.warning(f"Could not send fail DM to {user.name}: {e}")

    active_exams.pop(user.id, None)

    # حذف رسائل الاختبار من DM بعد 30 ثانية
    if result_msg:
        dm_message_ids.append(result_msg.id)
    asyncio.create_task(_cleanup_dm_messages(user, dm_message_ids))


async def handle_exam_timeout(bot: discord.Client, user: discord.User):
    """
    معالجة انتهاء وقت السؤال دون إجابة.
    """
    exam = active_exams.pop(user.id, None)
    if exam:
        lang = exam.get("lang", "ar")
        copy = ONBOARDING_COPY.get(lang, ONBOARDING_COPY["ar"])
        dm_message_ids = list(exam.get("dm_message_ids", []))

        timeout_msg = None
        try:
            timeout_msg = await user.send(copy["timeout_msg"])
        except Exception:
            pass

        if timeout_msg:
            dm_message_ids.append(timeout_msg.id)
        asyncio.create_task(_cleanup_dm_messages(user, dm_message_ids))

        log.info(f"Exam timed out for user {user.name} ({user.id})")
