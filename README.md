# 🚀 DevQuest Engine — Technical Certification & Daily Coding Ecosystem

DevQuest هو نظام مجتمعي متكامل عالي الأداء لمجتمعات البرمجة والتطوير على Discord. يجمع البوت بين **التحديات اليومية المحفزة (ByteDaily)** و**نظام الاختبارات التقنية للحصول على الرتب البرمجية (DM Certification Exam System)**، مع توفير دعم كامل ثنائي اللغة (عربي / إنجليزي) وبنية تحتية فائقة الاستقرار والسرعة.

---

## 🌟 المميزات الرئيسية (Core Features)

### 1. ⚡ نظام التحديات اليومية (ByteDaily Gamification Engine)
- **تحديات يومية مدعومة بالذكاء الاصطناعي**: توليد أسئلة تقنية متجددة يومياً عبر Gemini AI في مجالات متعددة (Backend, Laravel/PHP, SQL, Python, JS/TS, Docker, Git, C#).
- **إخفاء التصويت المقارن (Anti-Bandwagon Vote Masking)**: إخفاء نسبة وتوزيع الإجابات في البطاقة العامة للحد من التأثر بآراء الأغلبية، وتكشف الإحصائيات فقط للمستخدم في رسالة خفية (Ephemeral) بعد الإجابة.
- **نظام السلسلة والمتتالية (Streak System & Milestone Bonuses)**:
  - تتبع الإجابات المتتالية اليومية لكل عضو.
  - مكافآت نقاط إضافية عند تحقيق إنجازات متتالية (`+10` نقاط عند 5 أيام، `+30` نقطة عند 10 أيام).
  - بطاقات احتفالية عامة خلفيتها ذهبية (`#FFD700`) للإعلان عن إنجازات الأعضاء الجدد في القناة العامة.
- **التخزين المؤقت في الذاكرة (In-Memory Active Poll Cache)**: استجابة لحظية دون استعلام قاعدة البيانات مع كل ضغطة زر.
- **طابور الأسئلة المسبق (Pre-Generated Question Buffer Queue)**: الاحتفاظ بحوض مسبق من الأسئلة لضمان عدم توقف التحدي عند انقطاع شبكة AI.

### 2. 🎓 نظام الاختبارات التقنية في الخاص (DM Certification Exam System)
- **تجربة تفاعلية كاملة داخل الـ DM**: إرسال الأسئلة واختيار المسارات التخصصية مباشرة في الرسائل الخاصة للحفاظ على خصوصية الاختبار وتجنب الإزعاج.
- **تحديد المسار والتخصص (Select Path)**: دعم لكافة التخصصات البرمجية:
  - Frontend Developer
  - Backend Developer
  - Full-Stack Developer
  - Mobile Developer
  - Software Engineer
  - Security Engineer
  - Systems / Solutions Architect
- **منح الرتب التلقائي (Automated Role Awarding)**: عند اجتياز الاختبار بنسبة 100%، يمنح البوت العضو الرتبة المخصصة لتخصصه تلقائياً ونشر بطاقة تهنئة رسمية في القناة العامة.

### 3. 🛡️ التحصين الأمني وقواعد منع التحايل (Exam Security & Anti-Abuse)
- **تنبيه أحمر بارز قبل البدء (Red Warning Embed)**: تحذير شفاف يوضح كافة شروط الاختبار وبند الظروف القاهرة قبل الانطلاق.
- **قفل الجلسة النشطة (Active Session Lock)**: منع العضو من بدء أكثر من اختبار متزامن.
- **نقطة عدم العودة (Point of No Return)**: بمجرد ظهور السؤال الأول، يُحظر تغيير التخصص أو اللغة.
- **جزاء الانسحاب (Abandonment Penalty)**: أي انسحاب عبر `/cancel-exam` أو انتهاء الوقت (60 ثانية) يُحسب كـ "رسوب رسمي" ويُفعل حظر إعادة الاختبار للتخصص لمدة أسبوع كامل (1-Week Cooldown).
- **أداة إعادة ضبط الحظر للإدارة (`/reset-exam-cooldown`)**: إمكانية تدخل الإدارة لإعادة ضبط الوقت للمستخدمين عند حدوث مشكلة تقنية أو ظرف قاهر.

### 4. 🌐 المحرك الذكي لتحديد اللغة (Smart Bilingual Engine)
- دعم شامل لجميع الواجهات والنصوص والتفسيرات باللغتين العربية والإنجليزية.
- **هيكلية الأولوية لثلاث مستويات (3-Tier Hierarchy Resolution)**:
  1. **تفضيل قاعدة البيانات الصريح (Priority 1)**: خيار العضو المباشر المجهّز في قاعدة البيانات (`preferred_language`).
  2. **رتب السيرفر (Priority 2)**: اكتشاف لغة العضو بناءً على رتبة `English` أو `Arabic` في السيرفر.
  3. **الخيار الافتراضي (Priority 3)**: العودة التلقائية للغة العربية (`'ar'`).

---

## 🏗️ البنية التحتية والاعتمادية (Architecture & Reliability)

```
[ Discord Gateway ]
         │
         ▼
[ Interaction Layer / Views ]
         │
         ├──► [ Active Poll In-Memory Cache ] ──► (Instant Ephemeral Response)
         │
         ├──► [ Bilingual Resolution Engine ] ──► (DB Preference -> Server Role -> Fallback)
         │
         └──► [ PostgreSQL / Supabase Pool ] ───► (Asyncpg Connection Management)
                     ▲
                     │ (Buffer Queue & Fallback)
             [ Gemini AI API ] ◄──► [ Circuit Breaker Pattern ]
```

- **تجميع الاتصالات السريع (`asyncpg` Connection Pooling)**: إدارة الاتصالات بقاعدة البيانات بكفاءة عالية ومنع الاختناقات عبر فحص دوري لمعدل الاستخدام (80%+ Alert).
- **قاطع الدائرة للذكاء الاصطناعي (Circuit Breaker Pattern)**: حماية التحدي اليومي عند حدوث انقطاع أو تجاوز حدود الاستخدام (`Rate Limits` 429/503) لخدمة Gemini بتجميد الطلبات تلقائياً والاعتماد على طابور الأسئلة المسبق.
- **تتبع الأخطاء السحابي (Sentry Integration)**: تسجيل الأخطاء غير المتوقعة مرفقة بسياق المستخدم والتفاعل (`user_id`, `guild_id`, `custom_id`).
- **السجلات الهيكلية (`structlog`)**: طباعة الأحداث وسير التفاعلات بصيغة JSON مقروءة ومفهرسة مع قياس الأداء والزمن المنقضي (`duration_ms`).

---

## 🛠️ تقنيات المشروع (Tech Stack)

| التقنية | الاستخدام |
| :--- | :--- |
| **Python 3.11+** | لغة البرمجة الأساسية |
| **Discord.py 2.3+** | إطار عمل التفاعل مع Discord API |
| **PostgreSQL / Supabase** | قاعدة البيانات الرئيسية |
| **asyncpg** | محرك الربط السريع والسلس بقواعد البيانات Async |
| **Sentry SDK & structlog** | مراقبة الأخطاء، التتبع السحابي والسجلات الهيكلية |
| **Google Gemini AI API** | توليد الأسئلة التقنية والشروحات البرمجية |

---

## 🗄️ مخطط قاعدة البيانات (Database Schema Overview)

- **`bd_users`**: بيانات الأعضاء، النقاط الإجمالية، السلسلة الحالية (`current_streak`)، أعلاها (`highest_streak`)، والتفضيل اللغوي (`preferred_language`).
- **`bd_polls`**: الأسئلة اليومية المنشورة، الخيارات، الإجابات الصحيحة، والتفسيرات باللغتين العربية والإنجليزية.
- **`bd_answers`**: إجابات المستخدمين اليومية لمنع التكرار وحساب إحصائيات التوزيع.
- **`bd_questions`**: حوض الأسئلة المسبق التوليد بانتظار النشر الآلي.
- **`exam_cooldowns`**: سجل حظر التخصصات المجهزة بعد الرسوب أو التراجع (فترة 7 أيام).

---

## 📜 الأوامر المتاحة (Slash Commands)

### 👤 أوامر الأعضاء (User Commands)

| الأمر | الوصف |
| :--- | :--- |
| `/bytedaily-language` | تغيير تفضيل اللغة للتحدي اليومي (عربي / English / تلقائي حسب الرتبة). |
| `/exam` | بدء جلسة اختبار تقني وتحديد المسار البرمجي في الخاص (DM). |
| `/cancel-exam` | إلغاء جلسة الاختبار الحالية (تتحول لرسوب وحظر أسبوع إذا بدأت الأسئلة). |

### 🛠️ أوامر المشرفين (Admin Commands)

| الأمر | الوصف |
| :--- | :--- |
| `/bytedaily-force-cycle` | إجبار البوت على إنهاء التحدي الحالي ونشر تحدٍ يومي جديد فوراً. |
| `/reset-exam-cooldown` | إعادة ضبط حظر التخصصات لمستخدم معين في حالات الظروف القاهرة. |

---

## 🚀 التشغيل والتثبيت (Setup & Installation)

### 1. المتطلبات الأساسية
- Python 3.11 أو أحدث.
- قاعدة بيانات PostgreSQL أو حساب على Supabase.
- مفتاح تطبيق Discord Bot Token & Google Gemini API Key.

### 2. خطوات التثبيت

```bash
# 1. استنساخ المستودع
git clone https://github.com/ahmads2006/DevQuest.git
cd DevQuest

# 2. إنشاء البيئة الافتراضية وتفعيلها
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# 3. تثبيت المكتبات
pip install -r requirements.txt
```

### 3. إعداد متغيرات البيئة (`.env`)

قم بإنشاء ملف `.env` في المجلد الرئيسي بالقيم التالية:

```env
DISCORD_TOKEN=your_discord_bot_token
DATABASE_URL=postgresql://user:password@host:port/dbname
GEMINI_API_KEY=your_gemini_api_key
SENTRY_DSN=your_sentry_dsn_optional

BD_ROLE_ENGLISH=English
BD_ROLE_ARABIC=Arabic
```

### 4. تشغيل البوت

```bash
python main.py
```

---

## 📄 الترخيص (License)

هذا المشروع طُوّر لصالح مجتمع **Programming & Dev** تحت إدارة **أحمد الحروب**. جميع الحقوق محفوظة © 2026.