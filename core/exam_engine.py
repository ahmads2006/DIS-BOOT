# ======================
# ← منطق الاختبار
# ======================

# core/exam_engine.py

import time
import discord
from core.state import active_exams, cooldowns
from core.cooldowns import COOLDOWN
from DATA import get_random_questions

async def start_exam_core(user, guild_id, role):
    now = time.time()

    if user.id in cooldowns and role in cooldowns[user.id]:
        remaining = max(0, int((cooldowns[user.id][role] - now) / 3600))
        return ("cooldown", remaining)

    selected_questions = get_random_questions(role, count=3)
    if not selected_questions:
        return ("no_questions",)

    active_exams[user.id] = {
        "role": role,
        "index": 0,
        "guild_id": guild_id,
        "selected_questions": selected_questions,
    }

    try:
        dm = await user.create_dm()
        await dm.send("🧪 بدأ الاختبار! بالتوفيق 🍀")
        return ("ok", dm)
    except discord.Forbidden:
        active_exams.pop(user.id, None)
        return ("dm_forbidden",)
async def start_exam(interaction, role):
    result = await start_exam_core(user, guild_id, role)
    if result[0] == "cooldown":
        try:
            await interaction.followup.send(
                f"⛔ لا يمكنك إعادة اختبار **{role}** إلا بعد {result[1]} ساعة.",
                ephemeral=True,
            )
        except Exception as e:
            print(f"Error sending cooldown message: {e}")
        return
    if result[0] == "no_questions":
        try:
            await interaction.followup.send(
                "❌ لا توجد أسئلة متاحة لهذا الاختبار حاليًا.",
                ephemeral=True,
            )
        except Exception as e:
            print(f"Error sending no-questions message: {e}")
        return
    if result[0] == "dm_forbidden":
        try:
            await interaction.followup.send("❌ افتح الخاص أولاً.", ephemeral=True)
        except Exception as e:
            print(f"Error sending DM error message: {e}")
        return
    # result[0] == "ok"
    try:
        await interaction.followup.send("📩 تم إرسال الاختبار إلى الخاص.", ephemeral=True)
    except Exception as e:
        print(f"Error sending exam started message: {e}")
        return
    return result[1]