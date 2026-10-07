import os
from pathlib import Path

# تحميل متغيرات البيئة من .env
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val

_load_env()

# إعدادات ديسكورد الأساسية
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID") or "0")  # 0 يعني المزامنة العامة، أو معرف السيرفر للمزامنة السريعة

# إعدادات الرتب والقنوات
PUBLIC_LOG_CHANNEL_NAME = os.getenv("LOG_CHANNEL", "╔〖💬┇〢general・chat")

RULES_ACCEPTED_ROLE_NAMES = [
    "👥 | Member",
    "✔ Rules Accepted",
    "Rules Accepted",
    "Member",
    "Verified",
    "🌱 | Intern",
    "Intern",
    "عضو",
    "مفعل",
]

# خريطة الرتب مطابقة تماماً لرتب السيرفر
ROLE_MAP = {
    "frontend": "🎨 | Frontend Developer",
    "backend": "🔧 | Backend Developer",
    "solutions_architect": "🏗️ | Solutions Architect",
    "system_architect": "🖥️ | System Architect",
    "security_engineer": "🛡️ |Security Engineer",
    "software_engineer": "💻 | Software Engineer",
    "fullstack_developer": "⚙️ | Full-Stack Developer",
    "mobile_developer": "📱 | Mobile Developer",
    "junior_developer": "📝 | Junior Developer",
}

# بيانات وألوان رتب التخصصات
TRACK_ROLE_METADATA = {
    "frontend": {"name": "🎨 | Frontend Developer", "color": 0x3498DB},
    "backend": {"name": "🔧 | Backend Developer", "color": 0x2ECC71},
    "solutions_architect": {"name": "🏗️ | Solutions Architect", "color": 0xE67E22},
    "system_architect": {"name": "🖥️ | System Architect", "color": 0x9B59B6},
    "security_engineer": {"name": "🛡️ |Security Engineer", "color": 0xE74C3C},
    "software_engineer": {"name": "💻 | Software Engineer", "color": 0x1ABC9C},
    "fullstack_developer": {"name": "⚙️ | Full-Stack Developer", "color": 0xF1C40F},
    "mobile_developer": {"name": "📱 | Mobile Developer", "color": 0x95A5A6},
    "junior_developer": {"name": "📄 | Junior Developer", "color": 0x7289DA},
}

# خريطة رتب المستويات البرمجية (ByteDaily Developer Tier Roles)
TIER_ROLES = [
    {
        "key": "tier_legendary",
        "name": "👑 | Legendary Architect",
        "min_points": 500,
        "color": 0xF1C40F,  # Gold
        "title_en": "Legendary Architect",
        "title_ar": "مهندس برمجيات أسطوري",
    },
    {
        "key": "tier_lead",
        "name": "💎 | Lead Engineer",
        "min_points": 250,
        "color": 0x1ABC9C,  # Teal
        "title_en": "Lead Engineer",
        "title_ar": "قائد تقني متميز",
    },
    {
        "key": "tier_senior",
        "name": "🚀 | Senior Developer",
        "min_points": 100,
        "color": 0x9B59B6,  # Purple
        "title_en": "Senior Developer",
        "title_ar": "مطور برمجيات متقدم",
    },
    {
        "key": "tier_coder",
        "name": "⚡ | Full-Stack Coder",
        "min_points": 40,
        "color": 0x3498DB,  # Blue
        "title_en": "Full-Stack Coder",
        "title_ar": "مبرمج متمرس",
    },
    {
        "key": "tier_junior",
        "name": "🥉 | Junior Dev",
        "min_points": 10,
        "color": 0xE67E22,  # Orange
        "title_en": "Junior Dev",
        "title_ar": "مطور واعد",
    },
]


# إعدادات الاختبارات
QUESTIONS_COUNT = 3
QUESTION_TIMEOUT_SECONDS = 60  # 60 ثانية لكل سؤال
COOLDOWN_SECONDS = 7 * 24 * 60 * 60  # أسبوع

# إعدادات الـ API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5000"))
_DEFAULT_BOT_API_KEY = "secret123"
BOT_API_KEY = os.getenv("BOT_API_KEY", _DEFAULT_BOT_API_KEY)


def _validate_production_secrets() -> None:
    """Refuse weak/missing API keys on Render (public HTTP surface)."""
    if "RENDER" not in os.environ:
        return
    key = (BOT_API_KEY or "").strip()
    if not key or key == _DEFAULT_BOT_API_KEY:
        raise RuntimeError(
            "Production (Render): set a strong BOT_API_KEY in environment variables. "
            "The default 'secret123' and empty values are not allowed."
        )


_validate_production_secrets()

# إعدادات قاعدة البيانات (PostgreSQL / Supabase)
DATABASE_URL = os.getenv("DATABASE_URL", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# النصوص والترجمات للأونبوردنغ والاختبارات التقنية
ONBOARDING_INITIAL_PROMPT = "Choose your language / اختر اللغة:"

EXAM_BILINGUAL_COPY = {
    "ar": {
        "landing_title": "🧪 نظام الاختبارات التقنية وتحديد المستوى",
        "landing_desc": (
            "🎯 **مرحباً بك في نظام التقييم البرمجي المعتمد!**\n\n"
            "هذا الاختبار يتيح لك إثبات خبرتك التقنية والحصول على رتبة المطور المعتمد في السيرفر.\n"
            "يرجى اختيار لغة الاختبار المفضلة للمتابعة أدناه:"
        ),
        "track_select_title": "🧪 نظام الاختبارات التقنية • اختيار المسار",
        "track_select_desc": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 **اختر تخصصك البرمجي من القائمة المنسدلة أدناه لبدء الاختبار:**\n\n"
            "📋 **تعليمات وقواعد الاختبار:**\n"
            "• 📝 عدد الأسئلة: **3 أسئلة تقنية**\n"
            "• ⏱️ الوقت المتاح: **60 ثانية لكل سؤال**\n"
            "• 🎯 شرط الاجتياز: **الإجابة الصحيحة بنسبة 100%**\n"
            "• 🏷️ عند النجاح: **تُمنح الرتبة تلقائياً وتُعلن في الشات العام**\n"
            "• ⏳ في حال عدم الاجتياز: **فترة انتظار أسبوع لنفس التخصص**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "track_select_placeholder": "🔽 اختر تخصصك البرمجي لبدء الاختبار...",
        "track_locked": "✅ تم تثبيت المسار وبدء الاختبار...",
        "change_lang_btn": "🌐 تغيير اللغة / Change Language",
        "cooldown_msg": "لا يمكنك إعادة هذا الاختبار حالياً. يرجى الانتظار",
        "cooldown_hours": "ساعة",
        "no_questions": "❌ لا توجد أسئلة متاحة لهذا المسار حالياً.",
        "active_exam_exists": "⚠️ لديك اختبار نشط بالفعل في الرسائل الخاصة.",
        "dm_closed": "❌ لا أستطيع إرسال رسائل خاصة لك. يرجى تفعيل الرسائل المباشرة في إعدادات السيرفر ثم المحاولة مجدداً.",
        "timeout_msg": "⏰ انتهى الوقت المحدد للسؤال (60 ثانية)! تم إلغاء جلسة الاختبار الحالية.",
        "exam_cancel": "❌ تم إلغاء جلسة الاختبار بنجاح.",
        "question_title": "السؤال {index} من {total} • الاختبار التقني",
        "progress_label": "مستوى التقدم",
        "option_label": "الخيار",
        "timer_footer": "⏰ الوقت: 60 ثانية • اختر الإجابة من الأزرار أدناه ⬇️",
        "success_title": "🎉 نتيجة الاختبار: اجتياز كامل!",
        "success_dm": (
            "🎉 **مبارك! لقد اجتزت الاختبار التقني بنجاح تام وتم منحك الرتبة في السيرفر.**\n\n"
            "🏷️ **الرتبة الممنوحة:** **{role_name}**\n"
            "📊 **الدرجة:** `{score}/{total}` (علامة كاملة 100% ⭐)\n\n"
            "✅ تم نشر بطاقة اعتمادك البرمجية في روم الشات العام بالسيرفر."
        ),
        "fail_title": "📊 نتيجة الاختبار: لم يتم الاجتياز",
        "fail_dm": (
            "❌ **لم تجتز الاختبار هذه المرة.**\n\n"
            "📊 **النتيجة المحققة:** `{score}/{total}` (المطلوب 100% للاجتياز)\n"
            "⛔ **فترة الانتظار:** يمكنك إعادة المحاولة بعد أسبوع لنفس التخصص.\n"
            "💡 **ملاحظة:** يمكنك تجربة اختبار مسار آخر في أي وقت."
        ),
        "explanation_header": "📖 الشرح والتوضيح",
        "cleanup_footer": "⏳ سيتم تنظيف وحذف محادثة هذا الاختبار تلقائياً خلال 30 ثانية...",
        "choose_level": "اختر مستواك البرمجي للبدء:",
        "beginner": "مبتدئ 🧑‍🎓",
        "professional": "محترف 🧑‍💻",
        "junior_done": "✅ تم منحك رتبة **📝 | Junior Developer**. مرحباً بك في المجتمع!",
        "choose_spec": "اختر تخصصك للانتقال إلى الاختبار التقني:",
        "exam_started": "🧪 تم إرسال الاختبار إلى رسائلك الخاصة. بالتوفيق! 🍀",
    },
    "en": {
        "landing_title": "🧪 Technical Assessment & Certification System",
        "landing_desc": (
            "🎯 **Welcome to the Certified Technical Evaluation System!**\n\n"
            "This assessment allows you to prove your engineering skills and earn your verified role in the server.\n"
            "Please select your preferred exam language below to proceed:"
        ),
        "track_select_title": "🧪 Technical Exam System • Select Your Track",
        "track_select_desc": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 **Select your programming track from the dropdown below to begin:**\n\n"
            "📋 **Exam Instructions & Rules:**\n"
            "• 📝 Question Count: **3 Technical Questions**\n"
            "• ⏱️ Time Limit: **60 seconds per question**\n"
            "• 🎯 Passing Score: **100% correct answers required**\n"
            "• 🏷️ On Passing: **Role is automatically assigned & announced in general chat**\n"
            "• ⏳ On Failure: **1-week cooldown for the same track**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "track_select_placeholder": "🔽 Select your programming track to begin...",
        "track_locked": "✅ Track locked. Starting exam...",
        "change_lang_btn": "🌐 تغيير اللغة / Change Language",
        "cooldown_msg": "You cannot retake this exam yet. Please wait",
        "cooldown_hours": "hour(s)",
        "no_questions": "❌ No questions available for this track at the moment.",
        "active_exam_exists": "⚠️ You already have an active exam in progress in your DMs.",
        "dm_closed": "❌ Cannot send you direct messages. Please enable DMs in server privacy settings and try again.",
        "timeout_msg": "⏰ Time is up for this question (60s)! The exam session has been cancelled.",
        "exam_cancel": "❌ Exam session has been cancelled successfully.",
        "question_title": "Question {index} of {total} • Technical Exam",
        "progress_label": "Progress",
        "option_label": "Option",
        "timer_footer": "⏰ Time: 60s • Choose your answer from the buttons below ⬇️",
        "success_title": "🎉 Exam Result: Passed with Distinction!",
        "success_dm": (
            "🎉 **Congratulations! You passed the technical exam with a perfect score and received your role!**\n\n"
            "🏷️ **Role Granted:** **{role_name}**\n"
            "📊 **Score:** `{score}/{total}` (100% ⭐)\n\n"
            "✅ Your certification badge has been announced in the server general chat."
        ),
        "fail_title": "📊 Exam Result: Not Passed",
        "fail_dm": (
            "❌ **You did not pass the exam this time.**\n\n"
            "📊 **Your Score:** `{score}/{total}` (100% required to pass)\n"
            "⛔ **Cooldown:** You can retry after 1 week for this same track.\n"
            "💡 **Tip:** You may explore and take an exam in a different track right away."
        ),
        "explanation_header": "📖 Explanation",
        "cleanup_footer": "⏳ This exam conversation will be automatically cleaned up in 30 seconds...",
        "choose_level": "Choose your programming level to begin:",
        "beginner": "Beginner 🧑‍🎓",
        "professional": "Professional 🧑‍💻",
        "junior_done": "✅ You have been granted the **📝 | Junior Developer** role. Welcome to the community!",
        "choose_spec": "Choose your specialization to continue to the technical exam:",
        "exam_started": "🧪 The exam has been sent to your DMs. Good luck! 🍀",
    },
}

# Alias for backward compatibility
ONBOARDING_COPY = EXAM_BILINGUAL_COPY

