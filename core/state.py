# ======================
# التخزين (dicts)
# ======================

active_exams = {}     # الامتحانات الحالية{user_id: {"role": role, "index": question_index, "guild_id": guild_id, "selected_questions": []}}
cooldowns = {}       # {user_id: {role: timestamp}}
onboarding_sent_to = set()  # {user_id} لمنع إرسال الأونبوردنغ مرتين