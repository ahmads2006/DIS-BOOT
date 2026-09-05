<<<<<<< HEAD
from typing import Dict, Any, Set

# active_exams structure:
# {
#    user_id: {
#        "role": str,
#        "guild_id": int,
#        "index": int,
#        "selected_questions": list,
#        "score": int,
#        "start_time": float,
#        "lang": str
#    }
# }
active_exams: Dict[int, Dict[str, Any]] = {}

# Set of user IDs to prevent sending onboarding duplicate DMs in a single session
onboarding_sent_to: Set[int] = set()
=======
# ======================
# التخزين (dicts)
# ======================

active_exams = {}     # الامتحانات الحالية{user_id: {"role": role, "index": question_index, "guild_id": guild_id, "selected_questions": []}}
cooldowns = {}       # {user_id: {role: timestamp}}
onboarding_sent_to = set()  # {user_id} لمنع إرسال الأونبوردنغ مرتين
>>>>>>> 3bb9071507dbfdff348f8abb94a36dd22d51eb70
