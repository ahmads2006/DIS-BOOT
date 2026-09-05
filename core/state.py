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