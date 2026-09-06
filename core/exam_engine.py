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


def find_role_smart(guild: discord.Guild, role_key: str) -> Optional[discord.Role]:
    """
    البحث الذكي عن الرتبة في السيرفر مع مراعاة الإيموجي والمسافات والرموز الزخرفية.
    """
    configured_name = ROLE_MAP.get(role_key, "")
    
    # 1. مطابقة بالاسم المضبوط من الكونفيج
    if configured_name:
        role = discord.utils.get(guild.roles, name=configured_name)
        if role:
            return role

    # 2. كلمات مفتاحية لكل مسار للبحث المرن في حال تغيّر الإيموجي
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
    """
    البحث الذكي عن روم الشات العام / الإعلانات لإرسال بطاقة الإنجاز.
    """
    preferred_names = [
        PUBLIC_LOG_CHANNEL_NAME,
        "╔〖💬┇〢general・chat",
        "general・chat",
        "general-chat",
        "general_chat",
        "general",
        "عام",
        "شات-عام",
        "chat"
    ]

    # 1. فحص الأسماء المباشرة
    for name in preferred_names:
        ch = discord.utils.get(guild.text_channels, name=name)
        if ch:
            return ch

    # 2. فحص مرن لأي قناة تحتوي على general أو chat أو عام
    for ch in guild.text_channels:
        ch_name = ch.name.lower()
        if "general" in ch_name or "chat" in ch_name or "عام" in ch_name:
            return ch

    return None


async def start_exam_core(bot: discord.Client, user: discord.User, guild_id: int, role_key: str, lang: str = "ar") -> Tuple[str, Any]:
    """
    بدء اختبار جديد للمستخدم.
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

    # حفظ حالة الاختبار
    active_exams[user.id] = {
        "role": role_key,
        "guild_id": guild_id,
        "index": 0,
        "selected_questions": questions,
        "score": 0,
        "start_time": time.time(),
        "lang": lang,
        "current_message_id": None,
        "dm_message_ids": [],
    }

    log.info(f"Exam started: user={user.name} ({user.id}), role={role_key}")
    return ("ok", dm)


async def send_next_question(bot: discord.Client, user: discord.User, dm_channel: discord.DMChannel):
    """
    إرسال السؤال التالي للمستخدم بتصميم مدمج وواضح وشبكة خيارات 2x2.
    """
    exam = active_exams.get(user.id)
    if not exam:
        return

    from views.exam_views import QuestionView

    current_idx = exam["index"]
    total = len(exam["selected_questions"])
    q_data = exam["selected_questions"][current_idx]

    # شريط التقدم الرسومي
    filled = int(((current_idx + 1) / total) * 6)
    progress_bar = "▰" * filled + "▱" * (6 - filled)
    percent = int(((current_idx + 1) / total) * 100)

    opt_a = q_data["c"].get("A", "")
    opt_b = q_data["c"].get("B", "")
    opt_c = q_data["c"].get("C", "")
    opt_d = q_data["c"].get("D", "")

    embed = discord.Embed(
        title=f"📝 السؤال {current_idx + 1} من {total} • Technical Exam",
        description=(
            f"📊 **مستوى التقدم:** `[{progress_bar}] {percent}%`\n\n"
            f"## ❓ **{q_data['q']}**\n"
            f"────────────────────────"
        ),
        color=discord.Color.from_rgb(88, 101, 242)
    )

    # شبكة الخيارات 2x2 (A بجانب B، وتحتهما C بجانب D)
    embed.add_field(name="🔹 الخيار A", value=f"> **{opt_a}**", inline=True)
    embed.add_field(name="🔹 الخيار B", value=f"> **{opt_b}**", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # فاصل عمود ثالث لضبط الصف الأول

    embed.add_field(name="🔹 الخيار C", value=f"> **{opt_c}**", inline=True)
    embed.add_field(name="🔹 الخيار D", value=f"> **{opt_d}**", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # فاصل عمود ثالث لضبط الصف الثاني

    embed.set_footer(
        text=f"⏰ الوقت: {QUESTION_TIMEOUT_SECONDS} ثانية • اختر الإجابة من الأزرار أدناه ⬇️"
    )

    view = QuestionView(bot=bot, user=user, timeout_seconds=QUESTION_TIMEOUT_SECONDS)
    msg = await dm_channel.send(embed=embed, view=view)
    exam["current_message_id"] = msg.id
    exam["dm_message_ids"].append(msg.id)


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
        total = len(exam["selected_questions"])
        passed = (exam["score"] == total)

        if passed:
            await handle_exam_success(bot, user, exam)
        else:
            await handle_exam_fail(bot, user, exam)


async def _cleanup_dm_messages(user: discord.User, message_ids: list):
    """
    حذف جميع رسائل الاختبار من DM بعد 30 ثانية لتنظيف المحادثة.
    """
    try:
        await asyncio.sleep(30)
        dm = await user.create_dm()
        for msg_id in message_ids:
            try:
                msg = await dm.fetch_message(msg_id)
                await msg.delete()
                await asyncio.sleep(0.4)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        log.info(f"Cleaned up {len(message_ids)} exam DM messages for {user.name}")
    except Exception as e:
        log.warning(f"Error cleaning up DM messages for {user.name}: {e}")


async def handle_exam_success(bot: discord.Client, user: discord.User, exam: dict):
    """
    منح الرتبة فعلياً وإرسال بطاقة الإنجاز المزخرفة في روم الشات العام (general-chat).
    """
    role_key = exam["role"]
    guild_id = exam["guild_id"]
    lang = exam.get("lang", "ar")
    copy = ONBOARDING_COPY.get(lang, ONBOARDING_COPY["ar"])
    dm_message_ids = list(exam.get("dm_message_ids", []))

    guild = bot.get_guild(guild_id)
    role_obj = None
    role_name = ROLE_MAP.get(role_key, role_key)

    if guild:
        # 1. البحث الذكي عن الرتبة وإسنادها للمستخدم
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
                        await member.add_roles(role_obj, reason="اجتياز الاختبار التقني بنجاح")
                        log.info(f"Successfully granted role '{role_obj.name}' to {user.name}")
                    except discord.Forbidden:
                        log.error(f"Missing permissions (Manage Roles) to grant role '{role_obj.name}' to {user.name}")
                    except Exception as e:
                        log.error(f"Failed to add role '{role_obj.name}' to {user.name}: {e}")
                else:
                    top_name = bot_member.top_role.name if bot_member else "Unknown"
                    log.warning(
                        f"⚠️ خطأ في هرمية الرتب: رتبة البوت '{top_name}' ليست أعلى من الرتبة المطلوبة '{role_obj.name}' في سيرفر {guild.name}! "
                        f"يرجى سحب رتبة البوت في إعدادات السيرفر لتكون فوق رتب المطورين."
                    )
            else:
                log.error(f"Member with ID {user.id} not found in guild {guild.name}")
        else:
            log.warning(f"Could not find role matching '{role_key}' in guild {guild.name}")

        # 2. إرسال بطاقة التهنئة المزخرفة في روم الشات العام
        general_channel = find_announcement_channel(guild)
        if general_channel:
            try:
                role_display = role_obj.mention if role_obj else f"**{role_name}**"
                
                # بطاقة إنجاز مزخرفة وجميلة جداً
                cert_embed = discord.Embed(
                    title="🏆 شهادة اعتماد برمجية | Verified Certification",
                    description=(
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🎉 **نبارك للمبدع {user.mention} اجتيازه الاختبار التقني بنجاح تام!**\n\n"
                        f"🏷️ **الرتبة الممنوحة:** {role_display}\n"
                        f"📊 **النتيجة:** `{exam['score']}/{len(exam['selected_questions'])}` (علامة كاملة 100% ⭐)\n"
                        f"🏅 **الحالة:** **مطور معتمد | Certified Developer** 🚀\n\n"
                        f"> 💡 *تم تقييم المهارات التقنية واجتياز المعايير البرمجية بنجاح.* \n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=discord.Color.from_rgb(46, 204, 113)  # أخضر زمردي جذاب
                )
                
                # إضافة صورة العضو وصورة السيرفر
                user_avatar = user.display_avatar.url if hasattr(user, "display_avatar") else user.avatar.url if user.avatar else None
                if user_avatar:
                    cert_embed.set_thumbnail(url=user_avatar)
                
                guild_icon = guild.icon.url if guild.icon else None
                if guild_icon:
                    cert_embed.set_footer(text=f"{guild.name} • Technical Certification System", icon_url=guild_icon)
                else:
                    cert_embed.set_footer(text="Technical Certification System")

                await general_channel.send(content=f"📣 تهانينا الحارة لـ {user.mention} بمناسبة ترقيته الجديدة!", embed=cert_embed)
                log.info(f"Sent success announcement to channel {general_channel.name}")
            except Exception as e:
                log.error(f"Error sending certification announcement: {e}")

    # 3. إرسال بطاقة النتيجة للمستخدم في الخاص
    result_msg = None
    try:
        success_embed = discord.Embed(
            title="🎉 نتيجة الاختبار: اجتياز كامل!",
            description=(
                f"{copy['success_dm']}\n\n"
                f"🏷️ **الرتبة الممنوحة:** **{role_name}**\n"
                f"📊 **الدرجة:** `{exam['score']}/{len(exam['selected_questions'])}` (100%)\n\n"
                f"✅ تم نشر بطاقة اعتمادك في الشات العام بالسيرفر."
            ),
            color=discord.Color.green()
        )
        success_embed.set_footer(text="⏳ سيتم تنظيف وحذف محادثة هذا الاختبار تلقائياً خلال 30 ثانية...")
        result_msg = await user.send(embed=success_embed)
    except Exception as e:
        log.warning(f"Could not send success DM to {user.name}: {e}")

    # 4. التوثيق والحذف من الذاكرة
    await db.record_exam_attempt(user.id, role_key, exam["score"], passed=True)
    active_exams.pop(user.id, None)

    # 5. جدولة تنظيف رسائل الـ DM
    if result_msg:
        dm_message_ids.append(result_msg.id)
    asyncio.create_task(_cleanup_dm_messages(user, dm_message_ids))


async def handle_exam_fail(bot: discord.Client, user: discord.User, exam: dict):
    """
    تطبيق فترة الانتظار، إرسال رسالة توضيحية، وجدولة حذف الرسائل.
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
            description=(
                f"**النتيجة:** `{exam['score']}/{len(exam['selected_questions'])}`\n\n"
                f"{copy['fail_dm']}"
            ),
            color=discord.Color.red()
        )
        fail_embed.set_footer(text="⏳ سيتم تنظيف وحذف محادثة هذا الاختبار تلقائياً خلال 30 ثانية...")
        result_msg = await user.send(embed=fail_embed)
    except Exception as e:
        log.warning(f"Could not send fail DM to {user.name}: {e}")

    active_exams.pop(user.id, None)

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
