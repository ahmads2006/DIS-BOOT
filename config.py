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
    "✔ Rules Accepted",
    "Rules Accepted",
    "Member",
    "Verified",
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

# إعدادات الاختبارات
QUESTIONS_COUNT = 3
QUESTION_TIMEOUT_SECONDS = 60  # 60 ثانية لكل سؤال
COOLDOWN_SECONDS = 7 * 24 * 60 * 60  # أسبوع

# إعدادات الـ API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5000"))
BOT_API_KEY = os.getenv("BOT_API_KEY", "secret123")

# إعدادات قاعدة البيانات (PostgreSQL / Supabase)
DATABASE_URL = os.getenv("DATABASE_URL", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# النصوص والترجمات للأونبوردنغ
ONBOARDING_INITIAL_PROMPT = "Choose your language / اختر اللغة:"

ONBOARDING_COPY = {
    "ar": {
        "choose_lang": "اختر اللغة / Choose your language:",
        "beginner": "مبتدئ 🧑‍🎓",
        "professional": "محترف 🧑‍💻",
        "choose_level": "اختر مستواك البرمجي للبدء:",
        "junior_done": "✅ تم منحك رتبة **📝 | Junior Developer**. مرحباً بك في المجتمع!",
        "choose_spec": "اختر تخصصك للانتقال إلى الاختبار التقني:",
        "exam_started": "🧪 تم إرسال الاختبار إلى رسائلك الخاصة. بالتوفيق! 🍀",
        "dm_closed": "❌ لا أستطيع إرسال رسائل خاصة لك. يرجى فتح الرسائل الخاصة في إعدادات السيرفر ثم المحاولة مجدداً.",
        "cooldown_msg": "لا يمكنك إعادة هذا الاختبار حالياً. يرجى الانتظار",
        "timeout_msg": "⏰ انتهى الوقت المحدد للسؤال! تم إلغاء الاختبار.",
        "exam_cancel": "❌ تم إلغاء الاختبار.",
        "success_dm": "🎉 مبارك! لقد اجتزت الاختبار بنجاح وتم منحك الرتبة في السيرفر ✅",
        "fail_dm": "❌ لم تجتز الاختبار هذه المرة.\n⛔ يمكنك إعادة المحاولة بعد انتهاء فترة الانتظار (أسبوع).\n💡 يمكنك تجربة تخصص آخر الآن.",
        "active_exam_exists": "⚠️ لديك اختبار نشط بالفعل في الرسائل الخاصة.",
    },
    "en": {
        "choose_lang": "Choose your language:",
        "beginner": "Beginner 🧑‍🎓",
        "professional": "Professional 🧑‍💻",
        "choose_level": "Choose your programming level to begin:",
        "junior_done": "✅ You have been granted the **📝 | Junior Developer** role. Welcome to the community!",
        "choose_spec": "Choose your specialization to continue to the technical exam:",
        "exam_started": "🧪 The exam has been sent to your DMs. Good luck! 🍀",
        "dm_closed": "❌ I cannot send you DMs. Please enable direct messages in server privacy settings and try again.",
        "cooldown_msg": "You cannot retake this exam yet. Please wait",
        "timeout_msg": "⏰ Time is up for this question! The exam has been cancelled.",
        "exam_cancel": "❌ Exam cancelled.",
        "success_dm": "🎉 Congratulations! You passed the exam and received your role in the server ✅",
        "fail_dm": "❌ You did not pass the exam this time.\n⛔ You can retry after the 1-week cooldown.\n💡 You can try another specialization right now.",
        "active_exam_exists": "⚠️ You already have an active exam in progress in your DMs.",
    },
}
