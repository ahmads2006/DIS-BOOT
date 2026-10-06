"""
Exam Engine — Core logic for managing DM technical examinations and certifications.

Handles:
  - Starting exams and cooldown checks.
  - Delivering bilingual question embeds and timer management.
  - Processing answers and evaluating scores.
  - Assigning Discord roles on passing.
  - Sending bilingual DM outcome embeds and public certification announcements.
  - Auto-cleaning DM exam messages after 30 seconds.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
import discord

from config import (
    COOLDOWN_SECONDS,
    EXAM_BILINGUAL_COPY,
    PUBLIC_LOG_CHANNEL_NAME,
    QUESTION_TIMEOUT_SECONDS,
    QUESTIONS_COUNT,
    ROLE_MAP,
)
from legacy.core.database import db
from legacy.core.logger import log
from legacy.core.state import active_exams
from legacy.DATA import (
    get_explanation,
    get_options,
    get_question_text,
    get_random_questions,
    get_track_info,
)


def find_role_smart(guild: discord.Guild, role_key: str) -> Optional[discord.Role]:
    """
    Smart search for a Discord role matching the specialization key.
    Handles exact names, emojis, and common keywords.
    """
    configured_name = ROLE_MAP.get(role_key, "")
    if configured_name:
        role = discord.utils.get(guild.roles, name=configured_name)
        if role:
            return role

    keywords_map = {
        "frontend": ["frontend", "front-end", "فرونت"],
        "backend": ["backend", "back-end", "باك"],
        "fullstack_developer": ["full-stack", "fullstack", "full stack", "فول ستاك"],
        "mobile_developer": ["mobile", "موبايل"],
        "software_engineer": ["software engineer", "software", "برمجيات"],
        "security_engineer": ["security", "أمن", "حماية"],
        "solutions_architect": ["solutions architect", "solution", "حلول"],
        "system_architect": ["system architect", "system", "نظم"],
        "junior_developer": ["junior", "مبتدئ"],
    }

    keywords = keywords_map.get(role_key, [role_key.replace("_", " ")])
    for r in guild.roles:
        r_clean = r.name.lower()
        for kw in keywords:
            if kw in r_clean:
                return r

    return None


def find_announcement_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """Search for the main announcement / general chat channel."""
    preferred_names = [
        PUBLIC_LOG_CHANNEL_NAME,
        "╔〖💬┇〢general・chat",
        "general・chat",
        "general-chat",
        "general_chat",
        "general",
        "عام",
        "شات-عام",
        "chat",
    ]

    for name in preferred_names:
        ch = discord.utils.get(guild.text_channels, name=name)
        if ch:
            return ch

    for ch in guild.text_channels:
        ch_name = ch.name.lower()
        if "general" in ch_name or "chat" in ch_name or "عام" in ch_name:
            return ch

    return None


def build_exam_warning_embed() -> discord.Embed:
    """Build the prominent red warning embed displayed before Question 1."""
    embed = discord.Embed(
        title="⚠️ تنبيه هام جداً | Critical Warning Before Starting",
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🇸🇦 **تنبيهات وإرشادات هامة جداً قبل البدء:**\n"
            "• بمجرد ظهور السؤال الأول، تبدأ المحاولة الرسمية ولا يمكن تغيير اللغة أو التخصص.\n"
            "• عدم الإجابة خلال العد التنازلي (60 ثانية) أو إغلاق الجلسة أو استخدام `/cancel-exam` يُعد رسوباً رسمياً واستبعاداً تلقائياً يترتب عليه حظر إعادة الاختبار في هذا التخصص لمدة أسبوع كامل.\n"
            "• 💡 في حال وجود ظرف قاهر أو مشكلة تقنية خارجة عن إرادتك، يمكنك مراجعة إدارة السيرفر عبر التذاكر؛ وفي حال الموافقة يُعاد ضبط وقت محاولتك.\n\n"
            "🇬🇧 **Critical Instructions & Rules Before Starting:**\n"
            "• Once Question 1 is displayed, your session is locked. The language or track cannot be changed.\n"
            "• Exiting, timing out (60-second limit), or cancelling via the `/cancel-exam` command after the first question will result in the exam being marked as \"FAILED\" and trigger a one-week cooldown period for that track.\n"
            "• 💡 In cases of unexpected emergencies or technical force majeure, you may contact the administrators/staff via the ticketing system to request a reset of your cooldown period.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.red(),
    )
    embed.set_footer(text="DevQuest Exam System • Anti-Abuse & Integrity Policy")
    return embed


async def start_exam_core(
    bot: discord.Client,
    user: discord.User,
    guild_id: int,
    role_key: str,
    lang: str = "ar",
) -> Tuple[str, Any]:
    """Initialize a new exam session for a user."""
    if user.id in active_exams:
        return ("already_active",)

    # Cooldown check
    cooldown_rem = await db.get_cooldown_remaining(user.id, role_key)
    if cooldown_rem is not None:
        remaining_hours = max(1, int(cooldown_rem / 3600))
        return ("cooldown", remaining_hours)

    # Fetch questions
    selected_questions = get_random_questions(role_key, count=QUESTIONS_COUNT)
    if not selected_questions:
        log.warning(f"No questions found for role '{role_key}'")
        return ("no_questions",)

    # Create DM channel
    try:
        dm = await user.create_dm()
    except discord.Forbidden:
        log.warning(f"DMs are closed for user {user.name} ({user.id})")
        return ("dm_forbidden",)

    # Save active exam state
    active_exams[user.id] = {
        "role": role_key,
        "guild_id": guild_id,
        "index": 0,
        "selected_questions": selected_questions,
        "score": 0,
        "answers_history": [],
        "start_time": time.time(),
        "lang": lang,
        "current_message_id": None,
        "dm_message_ids": [],
        "state": "IN_PROGRESS",
    }

    log.info(f"Exam started: user={user.name} ({user.id}), role={role_key}, lang={lang}, state=IN_PROGRESS")
    return ("ok", dm)


async def send_next_question(
    bot: discord.Client,
    user: discord.User,
    dm_channel: discord.DMChannel,
) -> None:
    """Send the next bilingual question embed to the user in DMs."""
    exam = active_exams.get(user.id)
    if not exam:
        return

    from legacy.views.exam_views import QuestionView

    current_idx = exam["index"]
    total = len(exam["selected_questions"])
    q_data = exam["selected_questions"][current_idx]
    lang = exam.get("lang", "ar")
    copy = EXAM_BILINGUAL_COPY.get(lang, EXAM_BILINGUAL_COPY["ar"])

    # Progress bar
    filled = int(((current_idx + 1) / total) * 6)
    progress_bar = "▰" * filled + "▱" * (6 - filled)
    percent = int(((current_idx + 1) / total) * 100)

    # Localized text extraction
    question_text = get_question_text(q_data, lang=lang)
    opts = get_options(q_data, lang=lang)

    opt_a = opts.get("A", "")
    opt_b = opts.get("B", "")
    opt_c = opts.get("C", "")
    opt_d = opts.get("D", "")

    title = copy["question_title"].format(index=current_idx + 1, total=total)
    progress_label = copy["progress_label"]
    option_label = copy["option_label"]

    embed = discord.Embed(
        title=f"📝 {title}",
        description=(
            f"📊 **{progress_label}:** `[{progress_bar}] {percent}%`\n\n"
            f"## ❓ **{question_text}**\n"
            f"────────────────────────"
        ),
        color=discord.Color.from_rgb(88, 101, 242),
    )

    embed.add_field(name=f"🔹 {option_label} A", value=f"> **{opt_a}**", inline=True)
    embed.add_field(name=f"🔹 {option_label} B", value=f"> **{opt_b}**", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    embed.add_field(name=f"🔹 {option_label} C", value=f"> **{opt_c}**", inline=True)
    embed.add_field(name=f"🔹 {option_label} D", value=f"> **{opt_d}**", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    embed.set_footer(text=copy["timer_footer"])

    view = QuestionView(
        bot=bot, user=user, timeout_seconds=QUESTION_TIMEOUT_SECONDS
    )
    msg = await dm_channel.send(embed=embed, view=view)
    exam["current_message_id"] = msg.id
    exam["dm_message_ids"].append(msg.id)


async def process_answer(
    bot: discord.Client,
    user: discord.User,
    chosen_choice: str,
    interaction: discord.Interaction,
) -> None:
    """Evaluate submitted answer and proceed to the next question or complete exam."""
    exam = active_exams.get(user.id)
    if not exam:
        await interaction.response.send_message(
            "❌ انتهت جلسة الاختبار أو تم إلغاؤها / Exam session expired or was cancelled.",
            ephemeral=True,
        )
        return

    current_idx = exam["index"]
    q_data = exam["selected_questions"][current_idx]
    correct_choice = str(q_data.get("a", "")).strip().upper()
    is_correct = chosen_choice.upper() == correct_choice

    if is_correct:
        exam["score"] += 1

    exam["answers_history"].append(
        {
            "question": q_data,
            "chosen": chosen_choice.upper(),
            "correct": correct_choice,
            "is_correct": is_correct,
        }
    )

    exam["index"] += 1

    if exam["index"] < len(exam["selected_questions"]):
        dm_channel = user.dm_channel or await user.create_dm()
        await send_next_question(bot, user, dm_channel)
    else:
        total = len(exam["selected_questions"])
        passed = exam["score"] == total

        if passed:
            await handle_exam_success(bot, user, exam)
        else:
            await handle_exam_fail(bot, user, exam)


async def _cleanup_dm_messages(user: discord.User, message_ids: List[int]) -> None:
    """Delete transient exam DM messages after 30 seconds to keep chat clean."""
    try:
        await asyncio.sleep(30)
        dm = await user.create_dm()
        for msg_id in message_ids:
            try:
                msg = await dm.fetch_message(msg_id)
                await msg.delete()
                await asyncio.sleep(0.3)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        log.info(f"Cleaned up {len(message_ids)} exam DM messages for {user.name}")
    except Exception as e:
        log.warning(f"Error cleaning up DM messages for {user.name}: {e}")


async def handle_exam_success(
    bot: discord.Client,
    user: discord.User,
    exam: Dict[str, Any],
) -> None:
    """Award role, send bilingual announcement to general chat, and deliver localized success DM."""
    role_key = exam["role"]
    guild_id = exam["guild_id"]
    lang = exam.get("lang", "ar")
    copy = EXAM_BILINGUAL_COPY.get(lang, EXAM_BILINGUAL_COPY["ar"])
    dm_message_ids = list(exam.get("dm_message_ids", []))
    total_q = len(exam["selected_questions"])

    guild = bot.get_guild(guild_id)
    role_obj = None
    role_name = ROLE_MAP.get(role_key, role_key)

    if guild:
        role_obj = find_role_smart(guild, role_key)
        if role_obj:
            role_name = role_obj.name
            member = guild.get_member(user.id)
            if not member:
                try:
                    member = await guild.fetch_member(user.id)
                except Exception as e:
                    log.error(f"Could not fetch member {user.id} in guild {guild.name}: {e}")
                    member = None

            if member:
                bot_member = guild.me or guild.get_member(bot.user.id)
                if bot_member and bot_member.top_role > role_obj:
                    try:
                        await member.add_roles(
                            role_obj, reason="Passed technical certification exam"
                        )
                        log.info(f"Granted role '{role_obj.name}' to {user.name}")
                    except discord.Forbidden:
                        log.error(f"Missing permissions to grant role '{role_obj.name}' to {user.name}")
                    except Exception as e:
                        log.error(f"Failed to add role '{role_obj.name}' to {user.name}: {e}")
                else:
                    top_name = bot_member.top_role.name if bot_member else "Unknown"
                    log.warning(
                        f"⚠️ Bot role '{top_name}' is not higher than target role '{role_obj.name}' in {guild.name}!"
                    )

        # Send public celebration announcement in general chat
        general_channel = find_announcement_channel(guild)
        if general_channel:
            try:
                role_display = role_obj.mention if role_obj else f"**{role_name}**"
                track_info = get_track_info(role_key)

                cert_embed = discord.Embed(
                    title="🏆 شهادة اعتماد برمجية | Verified Technical Certification",
                    description=(
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🎉 **نبارك للمبدع / Congratulations to {user.mention}!**\n\n"
                        f"🏷️ **الرتبة الممنوحة / Granted Role:** {role_display}\n"
                        f"📊 **النتيجة / Score:** `{exam['score']}/{total_q}` (100% ⭐)\n"
                        f"🏅 **الحالة / Status:** **مطور معتمد | Certified Developer** 🚀\n\n"
                        f"> 💡 *تم تقييم المهارات التقنية واجتياز المعايير البرمجية بنجاح.*\n"
                        f"> 💡 *Successfully verified and demonstrated technical excellence.*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=discord.Color.from_rgb(46, 204, 113),
                )

                user_avatar = (
                    user.display_avatar.url
                    if hasattr(user, "display_avatar")
                    else (user.avatar.url if user.avatar else None)
                )
                if user_avatar:
                    cert_embed.set_thumbnail(url=user_avatar)

                guild_icon = guild.icon.url if guild.icon else None
                if guild_icon:
                    cert_embed.set_footer(
                        text=f"{guild.name} • Technical Certification System",
                        icon_url=guild_icon,
                    )
                else:
                    cert_embed.set_footer(text="Technical Certification System")

                await general_channel.send(
                    content=f"📣 تهانينا الحارة لـ {user.mention} بمناسبة ترقيته الجديدة! • Congratulations on your new certification!",
                    embed=cert_embed,
                )
                log.info(f"Sent certification announcement to #{general_channel.name}")
            except Exception as e:
                log.error(f"Error sending certification announcement: {e}")

    # Send localized DM success embed
    result_msg = None
    try:
        desc_text = copy["success_dm"].format(
            role_name=role_name,
            score=exam["score"],
            total=total_q,
        )
        success_embed = discord.Embed(
            title=copy["success_title"],
            description=desc_text,
            color=discord.Color.green(),
        )
        success_embed.set_footer(text=copy["cleanup_footer"])
        result_msg = await user.send(embed=success_embed)
    except Exception as e:
        log.warning(f"Could not send success DM to {user.name}: {e}")

    # Record attempt & cleanup memory
    await db.record_exam_attempt(user.id, role_key, exam["score"], passed=True)
    active_exams.pop(user.id, None)

    if result_msg:
        dm_message_ids.append(result_msg.id)
    asyncio.create_task(_cleanup_dm_messages(user, dm_message_ids))


async def handle_exam_fail(
    bot: discord.Client,
    user: discord.User,
    exam: Dict[str, Any],
) -> None:
    """Apply cooldown and deliver localized fail feedback DM."""
    role_key = exam["role"]
    lang = exam.get("lang", "ar")
    copy = EXAM_BILINGUAL_COPY.get(lang, EXAM_BILINGUAL_COPY["ar"])
    dm_message_ids = list(exam.get("dm_message_ids", []))
    total_q = len(exam["selected_questions"])

    await db.set_cooldown(user.id, role_key, COOLDOWN_SECONDS)
    await db.record_exam_attempt(user.id, role_key, exam["score"], passed=False)

    result_msg = None
    try:
        desc_text = copy["fail_dm"].format(
            score=exam["score"],
            total=total_q,
        )
        fail_embed = discord.Embed(
            title=copy["fail_title"],
            description=desc_text,
            color=discord.Color.red(),
        )

        # Include explanations for missed questions
        for item in exam.get("answers_history", []):
            if not item.get("is_correct"):
                q_item = item.get("question", {})
                q_txt = get_question_text(q_item, lang=lang)
                expl = get_explanation(q_item, lang=lang)
                if expl:
                    fail_embed.add_field(
                        name=f"❓ {q_txt[:80]}...",
                        value=f"💡 **{copy['explanation_header']}:** {expl}",
                        inline=False,
                    )

        fail_embed.set_footer(text=copy["cleanup_footer"])
        result_msg = await user.send(embed=fail_embed)
    except Exception as e:
        log.warning(f"Could not send fail DM to {user.name}: {e}")

    active_exams.pop(user.id, None)

    if result_msg:
        dm_message_ids.append(result_msg.id)
    asyncio.create_task(_cleanup_dm_messages(user, dm_message_ids))


async def handle_exam_timeout(bot: discord.Client, user: discord.User) -> None:
    """Handle question expiration without response: mark as FAILED and apply 1-week cooldown."""
    exam = active_exams.pop(user.id, None)
    if exam:
        role_key = exam["role"]
        lang = exam.get("lang", "ar")
        copy = EXAM_BILINGUAL_COPY.get(lang, EXAM_BILINGUAL_COPY["ar"])
        dm_message_ids = list(exam.get("dm_message_ids", []))

        # Apply strict 1-week cooldown & record failed attempt
        await db.set_cooldown(user.id, role_key, COOLDOWN_SECONDS)
        await db.record_exam_attempt(user.id, role_key, exam.get("score", 0), passed=False)

        timeout_msg = None
        try:
            timeout_title = (
                "⏰ انتهاء الوقت المحدد (رسوب) • Time Expired (FAILED)"
                if lang == "ar"
                else "⏰ Time Expired • Exam FAILED"
            )
            timeout_desc = (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🇸🇦 **انتهى الوقت المحدد للإجابة (60 ثانية) دون رد.**\n"
                "• تم اعتبار المحاولة ملغاة واحتسابها **رسوباً رسمياً**.\n"
                "• ⛔ تم تطبيق فترة انتظار لمدة **أسبوع كامل (7 أيام)** في هذا التخصص قبل السماح بإعادة المحاولة.\n"
                "• 💡 إذا واجهتك مشكلة تقنية طارئة، يمكنك التواصل مع إدارة السيرفر عبر التذاكر.\n\n"
                "🇬🇧 **The 60-second response timer has expired.**\n"
                "• The attempt has been marked as **FAILED**.\n"
                "• ⛔ A **1-week (7 days) cooldown period** has been applied for this track.\n"
                "• 💡 In cases of technical emergencies, you may contact the staff via a support ticket.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            timeout_embed = discord.Embed(
                title=timeout_title,
                description=timeout_desc,
                color=discord.Color.red(),
            )
            timeout_embed.set_footer(text=copy.get("cleanup_footer", "DevQuest Exam System"))
            timeout_msg = await user.send(embed=timeout_embed)
        except Exception as e:
            log.warning(f"Could not send timeout DM to {user.name}: {e}")

        if timeout_msg:
            dm_message_ids.append(timeout_msg.id)
        asyncio.create_task(_cleanup_dm_messages(user, dm_message_ids))

        log.info(f"Exam timed out for user {user.name} ({user.id}) — applied 1-week cooldown on {role_key}")
