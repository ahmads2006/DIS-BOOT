"""
DATA.py — Question Bank and Specialization Track Definitions for Technical Exams.

Provides mandatory bilingual (Arabic & English) pairings for:
  - Track names and descriptions (name_ar, name_en, desc_ar, desc_en)
  - Questions (question_ar, question_en)
  - Options (options_ar, options_en)
  - Explanations (explanation_ar, explanation_en)
  - Correct answers ('a' / 'correct_answer')
"""

import random
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Track & Specialization Metadata
# ─────────────────────────────────────────────────────────────────────────────

SPECIALIZATIONS: List[Dict[str, str]] = [
    {
        "value": "frontend",
        "emoji": "🎨",
        "name_ar": "مطور واجهات أمامية (Frontend Developer)",
        "name_en": "Frontend Developer",
        "desc_ar": "HTML5, CSS3, JavaScript, React, UI/UX, Responsive Design",
        "desc_en": "HTML5, CSS3, JavaScript, React, UI/UX, Responsive Design",
    },
    {
        "value": "backend",
        "emoji": "🔧",
        "name_ar": "مطور خلفيات برمجية (Backend Developer)",
        "name_en": "Backend Developer",
        "desc_ar": "Python, Node.js, قواعد البيانات, APIs, معمارية السيرفرات",
        "desc_en": "Python, Node.js, Databases, REST APIs, Server Architecture",
    },
    {
        "value": "fullstack_developer",
        "emoji": "⚙️",
        "name_ar": "مطور شامل (Full-Stack Developer)",
        "name_en": "Full-Stack Developer",
        "desc_ar": "معمارية مشتركة تجمع بين Frontend و Backend وقواعد البيانات",
        "desc_en": "Full end-to-end architecture bridging Frontend, Backend & DB",
    },
    {
        "value": "mobile_developer",
        "emoji": "📱",
        "name_ar": "مطور تطبيقات هواتف (Mobile Developer)",
        "name_en": "Mobile Developer",
        "desc_ar": "Flutter, React Native, iOS (Swift), Android (Kotlin)",
        "desc_en": "Flutter, React Native, iOS (Swift), Android (Kotlin)",
    },
    {
        "value": "software_engineer",
        "emoji": "💻",
        "name_ar": "مهندس برمجيات (Software Engineer)",
        "name_en": "Software Engineer",
        "desc_ar": "خوارزميات, هياكل بيانات, OOP, أنماط التصميم, Git",
        "desc_en": "Algorithms, Data Structures, OOP, Design Patterns, Git",
    },
    {
        "value": "security_engineer",
        "emoji": "🛡️",
        "name_ar": "مهندس أمن سيبراني (Security Engineer)",
        "name_en": "Security Engineer",
        "desc_ar": "الأمن السيبراني, اختبار الاختراق, التشفير, تأمين الشبكات",
        "desc_en": "Cybersecurity, PenTesting, Cryptography, Network Defense",
    },
    {
        "value": "solutions_architect",
        "emoji": "🏗️",
        "name_ar": "مهندس حلول سحابية (Solutions Architect)",
        "name_en": "Solutions Architect",
        "desc_ar": "الخدمات السحابية, القابلية للتوسع, توزيع الأحمال, توفر عالي",
        "desc_en": "Cloud Computing, Scalability, Load Balancing, High Availability",
    },
    {
        "value": "system_architect",
        "emoji": "🖥️",
        "name_ar": "مهندس أنظمة وبنية تحتية (System Architect)",
        "name_en": "System Architect",
        "desc_ar": "DevOps, CI/CD, الشبكات, أنظمة Linux, إدارة الحاويات",
        "desc_en": "DevOps, CI/CD, Networking, Linux Systems, Containerization",
    },
]

SPECIALIZATIONS_MAP: Dict[str, Dict[str, str]] = {
    spec["value"]: spec for spec in SPECIALIZATIONS
}


# ─────────────────────────────────────────────────────────────────────────────
# Bilingual Question Bank
# ─────────────────────────────────────────────────────────────────────────────

questions: Dict[str, List[Dict[str, Any]]] = {
    # ── 1. Frontend Developer ────────────────────────────────────────────────
    "frontend": [
        {
            "question_ar": "أي وسم HTML صحيح لتمثيل فقرة نصية أساسية؟",
            "question_en": "Which HTML element is the correct tag for paragraph text?",
            "options_ar": {"A": "<text>", "B": "<p>", "C": "<h>", "D": "<spanp>"},
            "options_en": {"A": "<text>", "B": "<p>", "C": "<h>", "D": "<spanp>"},
            "explanation_ar": "وسم <p> هو الوسم القياسي المخصص لكتابة الفقرات النصية في HTML.",
            "explanation_en": "The <p> tag is the standard HTML element used to define a paragraph.",
            "a": "B",
        },
        {
            "question_ar": "لربط ملف CSS خارجي بصفحة HTML نستخدم الوسم؟",
            "question_en": "Which HTML element is used to link an external CSS stylesheet?",
            "options_ar": {
                "A": "<style src='style.css'>",
                "B": "<css href='style.css'>",
                "C": "<link rel='stylesheet' href='style.css'>",
                "D": "<script href='style.css'>",
            },
            "options_en": {
                "A": "<style src='style.css'>",
                "B": "<css href='style.css'>",
                "C": "<link rel='stylesheet' href='style.css'>",
                "D": "<script href='style.css'>",
            },
            "explanation_ar": "يُستخدم الوسم <link> داخل <head> مع الخاصية rel='stylesheet' لربط ملفات CSS الخارجية.",
            "explanation_en": "The <link> tag with rel='stylesheet' inside <head> is used to link external CSS files.",
            "a": "C",
        },
        {
            "question_ar": "أي من الخيارات التالية يصف JavaScript بشكل أدق؟",
            "question_en": "Which statement most accurately describes JavaScript?",
            "options_ar": {
                "A": "لغة لتنسيق الألوان والنصوص فقط",
                "B": "لغة برمجة لإضافة التفاعل والمنطق لصفحات الويب",
                "C": "برنامج رسومي لتصميم المواقع",
                "D": "بروتوكول لنقل الملفات عبر الإنترنت",
            },
            "options_en": {
                "A": "A stylesheet language only for fonts and colors",
                "B": "A programming language that adds interactivity and logic to web pages",
                "C": "A graphic design software for websites",
                "D": "A file transfer protocol",
            },
            "explanation_ar": "جافاسكريبت هي لغة البرمجة المسؤولة عن المنطق والتفاعل في صفحات الويب الحديثة.",
            "explanation_en": "JavaScript is the programming language responsible for web page logic and interactivity.",
            "a": "B",
        },
        {
            "question_ar": "ما هي الخاصية الصحيحة في CSS لتغيير حجم الخط؟",
            "question_en": "Which CSS property is used to change font size?",
            "options_ar": {"A": "font-style", "B": "font-weight", "C": "font-size", "D": "text-size"},
            "options_en": {"A": "font-style", "B": "font-weight", "C": "font-size", "D": "text-size"},
            "explanation_ar": "الخاصية font-size هي المسؤولة عن تحديد حجم الخط بالبكسل أو rem أو غيرها.",
            "explanation_en": "The font-size property sets the size of the font (e.g. px, rem).",
            "a": "C",
        },
        {
            "question_ar": "لجعل العناصر تترتب أفقياً أو عمودياً بمرونة في CSS، أفضل طريقة حديثة هي؟",
            "question_en": "Which modern CSS display property is best for flexible 1D layouts?",
            "options_ar": {"A": "display: block;", "B": "display: inline;", "C": "display: flex;", "D": "display: table;"},
            "options_en": {"A": "display: block;", "B": "display: inline;", "C": "display: flex;", "D": "display: table;"},
            "explanation_ar": "نظام Flexbox يوفر مرونة فائقة في توزيع العناصر ومحاذاتها أفقياً وعمودياً.",
            "explanation_en": "CSS Flexbox provides powerful capabilities for aligning and distributing items flexibly.",
            "a": "C",
        },
        {
            "question_ar": "أي وسم HTML مخصص لإنشاء زر تفاعلي يمكن النقر عليه؟",
            "question_en": "Which semantic HTML element represents an interactive clickable button?",
            "options_ar": {"A": "<div>", "B": "<button>", "C": "<span>", "D": "<label>"},
            "options_en": {"A": "<div>", "B": "<button>", "C": "<span>", "D": "<label>"},
            "explanation_ar": "الوسم <button> هو الوسم القياسي القابل للوصول والمخصص للأزرار.",
            "explanation_en": "The <button> tag is the standard semantic and accessible element for buttons.",
            "a": "B",
        },
        {
            "question_ar": "لتغيير لون النص داخل عنصر في CSS نستخدم الخاصية؟",
            "question_en": "Which CSS property sets the foreground text color of an element?",
            "options_ar": {"A": "background-color", "B": "border-color", "C": "text-color", "D": "color"},
            "options_en": {"A": "background-color", "B": "border-color", "C": "text-color", "D": "color"},
            "explanation_ar": "خاصية color في CSS هي المسؤولة عن تلوين الخطوط والنصوص.",
            "explanation_en": "The CSS color property specifies the foreground text color of an element.",
            "a": "D",
        },
        {
            "question_ar": "ما هو مفهوم التصميم المتجاوب (Responsive Design)؟",
            "question_en": "What does Responsive Web Design mean?",
            "options_ar": {
                "A": "تصميم يعمل فقط على شاشات الحواسيب المكتبية",
                "B": "تصميم يتكيف بسلاسة مع مختلف مقاسات الشاشات والأجهزة",
                "C": "تصميم موقع بدون استخدام أي أكواد CSS",
                "D": "موقع لا يحتوي على أي صور أو ملفات وسائط",
            },
            "options_en": {
                "A": "Design that only functions on desktop monitors",
                "B": "Design that adapts dynamically to all screen sizes and devices",
                "C": "A web design built without CSS",
                "D": "A website containing no images or media",
            },
            "explanation_ar": "التصميم المتجاوب يضمن ظهور الموقع بشكل ممتاز على الهواتف والأجهزة اللوحية والحواسيب.",
            "explanation_en": "Responsive design ensures web pages render well on all screen sizes and devices.",
            "a": "B",
        },
        {
            "question_ar": "في Flexbox، أي خاصية تتحكم في اتجاه المحور الرئيسي (أفقي/عمودي)؟",
            "question_en": "In CSS Flexbox, which property controls the main axis direction?",
            "options_ar": {"A": "flex-wrap", "B": "justify-content", "C": "align-items", "D": "flex-direction"},
            "options_en": {"A": "flex-wrap", "B": "justify-content", "C": "align-items", "D": "flex-direction"},
            "explanation_ar": "الخاصية flex-direction تحدد اتجاه تدفق العناصر (row أو column).",
            "explanation_en": "flex-direction defines the main axis orientation (e.g., row or column).",
            "a": "D",
        },
        {
            "question_ar": "أي أداة مدمجة بالمتصفح تُستخدم لفحص العناصر وتجربة CSS في الوقت الفعلي؟",
            "question_en": "Which browser tool is used to inspect DOM elements and debug CSS live?",
            "options_ar": {"A": "DevTools (Inspect)", "B": "Photoshop", "C": "Word", "D": "PowerPoint"},
            "options_en": {"A": "DevTools (Inspect)", "B": "Photoshop", "C": "Word", "D": "PowerPoint"},
            "explanation_ar": "أدوات المطورين (DevTools) تتيح فحص الـ DOM والـ CSS وتصحيح أخطاء JavaScript.",
            "explanation_en": "Browser DevTools provide live inspection and debugging of DOM, CSS, and JavaScript.",
            "a": "A",
        },
    ],

    # ── 2. Backend Developer ─────────────────────────────────────────────────
    "backend": [
        {
            "question_ar": "ما هو الدور الأساسي للـ Backend في تطبيقات الويب؟",
            "question_en": "What is the primary role of the Backend in a web application?",
            "options_ar": {
                "A": "رسم الأيقونات وتلوين الأزرار",
                "B": "إدارة منطق الأعمال، قواعد البيانات، والعمليات على السيرفر",
                "C": "اختيار الخطوط المناسبة للمتصفح",
                "D": "كتابة المقالات الإعلانية",
            },
            "options_en": {
                "A": "Drawing icons and styling buttons",
                "B": "Managing business logic, databases, and server-side processing",
                "C": "Choosing fonts for the browser",
                "D": "Writing promotional copywriting",
            },
            "explanation_ar": "الـ Backend مسؤول عن معالجة البيانات، الحسابات، الأمان والاتصال بقواعد البيانات.",
            "explanation_en": "The Backend handles server processing, data validation, authentication, and database access.",
            "a": "B",
        },
        {
            "question_ar": "أي من التالي يعتبر لغة برمجة شائعة تُستخدم في تطوير الـ Backend؟",
            "question_en": "Which of the following is a prominent programming language used for Backend development?",
            "options_ar": {"A": "CSS", "B": "HTML", "C": "Python", "D": "Figma"},
            "options_en": {"A": "CSS", "B": "HTML", "C": "Python", "D": "Figma"},
            "explanation_ar": "لغة Python شائعة جداً في الـ Backend عبر أطر مثل FastAPI و Django.",
            "explanation_en": "Python is widely used in backend development with frameworks like FastAPI and Django.",
            "a": "C",
        },
        {
            "question_ar": "أي من التالي يصف قاعدة البيانات (Database) بشكل صحيح؟",
            "question_en": "Which of the following accurately describes a database?",
            "options_ar": {
                "A": "برنامج لتحرير الصور",
                "B": "نظام منظم لتخزين واسترجاع وإدارة البيانات بكفاءة",
                "C": "متصفح إنترنت",
                "D": "نظام تشغيل للحواسيب",
            },
            "options_en": {
                "A": "Image editing software",
                "B": "An organized system for storing, retrieving, and managing data",
                "C": "A web browser",
                "D": "A computer operating system",
            },
            "explanation_ar": "قاعدة البيانات تتيح حفظ البيانات واسترجاعها بسرعة وبشكل موثوق.",
            "explanation_en": "Databases provide structured, indexed, and reliable storage for application data.",
            "a": "B",
        },
        {
            "question_ar": "أي من التالي يعتبر نظام إدارة قواعد بيانات علائقية (Relational SQL)؟",
            "question_en": "Which of the following is a Relational SQL Database Management System?",
            "options_ar": {"A": "PostgreSQL / MySQL", "B": "React", "C": "CSS", "D": "HTML"},
            "options_en": {"A": "PostgreSQL / MySQL", "B": "React", "C": "CSS", "D": "HTML"},
            "explanation_ar": "PostgreSQL و MySQL هما من أشهر أنظمة قواعد البيانات العلائقية SQL.",
            "explanation_en": "PostgreSQL and MySQL are standard relational database management systems (RDBMS).",
            "a": "A",
        },
        {
            "question_ar": "ما هو الغرض الأساسي من استخدام لغة SQL؟",
            "question_en": "What is the primary purpose of SQL?",
            "options_ar": {
                "A": "تنسيق واجهات المستخدم",
                "B": "تصميم الألعاب ثلاثية الأبعاد",
                "C": "الاستعلام عن البيانات وتحديثها وإدارتها في قواعد البيانات",
                "D": "تشغيل الفيديوهات",
            },
            "options_en": {
                "A": "Styling user interfaces",
                "B": "Building 3D video games",
                "C": "Querying, updating, and managing structured database records",
                "D": "Streaming video media",
            },
            "explanation_ar": "لغة SQL تتيح قراءة وتعديل وحذف وإنشاء السجلات في قواعد البيانات.",
            "explanation_en": "SQL (Structured Query Language) is used to perform CRUD operations on relational data.",
            "a": "C",
        },
        {
            "question_ar": "ما هو الـ API (Application Programming Interface) في الـ Backend؟",
            "question_en": "What is an API in Backend architecture?",
            "options_ar": {
                "A": "تصميم رسومي لواجهة المستخدم",
                "B": "واجهة برمجية تتيح تواصل وتبادل البيانات بين التطبيقات والسيرفر",
                "C": "نوع من ملفات الصور",
                "D": "لوحة مفاتيح للحاسوب",
            },
            "options_en": {
                "A": "Graphical mockup of a user interface",
                "B": "An interface that allows applications and clients to exchange data with servers",
                "C": "An image file format",
                "D": "A computer hardware keyboard",
            },
            "explanation_ar": "الـ API يحدد نقاط النهاية (Endpoints) لتبادل البيانات بصيغ مثل JSON.",
            "explanation_en": "APIs define endpoints and protocols (e.g. REST/GraphQL) for data exchange.",
            "a": "B",
        },
        {
            "question_ar": "رمز الحالة 404 في بروتوكول HTTP يشير إلى؟",
            "question_en": "What does HTTP status code 404 indicate?",
            "options_ar": {
                "A": "الطلب نجح بالكامل (OK)",
                "B": "المورد المطلوب غير موجود (Not Found)",
                "C": "خطأ داخلي في السيرفر (Server Error)",
                "D": "طلب غير مصرح به (Unauthorized)",
            },
            "options_en": {
                "A": "Request succeeded (OK)",
                "B": "Requested resource not found (Not Found)",
                "C": "Internal Server Error",
                "D": "Unauthorized request",
            },
            "explanation_ar": "كود 404 يعني أن السيرفر لم يجد الصفحة أو المورد المطلوب.",
            "explanation_en": "HTTP 404 indicates the origin server did not find a current representation for the target resource.",
            "a": "B",
        },
        {
            "question_ar": "أي أداة تُستخدم لتتبع التغييرات في الكود والتعاون الجماعي في المشاريع؟",
            "question_en": "Which version control tool is standard for tracking code changes and collaboration?",
            "options_ar": {"A": "Git", "B": "Excel", "C": "PowerPoint", "D": "Paint"},
            "options_en": {"A": "Git", "B": "Excel", "C": "PowerPoint", "D": "Paint"},
            "explanation_ar": "نظام Git هو نظام إدارة النسخ القياسي لجميع المطورين.",
            "explanation_en": "Git is the distributed version control system used worldwide for tracking code history.",
            "a": "A",
        },
        {
            "question_ar": "إطار العمل Express.js يُستخدم في بيئة؟",
            "question_en": "Express.js is a popular web framework for which runtime environment?",
            "options_ar": {
                "A": "Node.js لبناء خوادم وAPIs",
                "B": "برامج تعديل الفيديو",
                "C": "متصفحات الويب فقط",
                "D": "قواعد بيانات Oracle",
            },
            "options_en": {
                "A": "Node.js for building web servers and REST APIs",
                "B": "Video editing software",
                "C": "Client-side browsers only",
                "D": "Oracle database engine",
            },
            "explanation_ar": "إطار Express.js مبني على Node.js لبناء خوادم وخدمات REST سريعة.",
            "explanation_en": "Express is a minimal and flexible Node.js web application framework.",
            "a": "A",
        },
        {
            "question_ar": "ما هي الميزة الأساسية التي يضيفها HTTPS مقارنة بـ HTTP العادي؟",
            "question_en": "What primary security enhancement does HTTPS provide over plain HTTP?",
            "options_ar": {
                "A": "ألوان وثيمات جديدة",
                "B": "تقليل حجم الخطوط",
                "C": "تشفير وحماية البيانات المنقولة عبر شهادة SSL/TLS",
                "D": "إضافة إعلانات تلقائية",
            },
            "options_en": {
                "A": "New color themes",
                "B": "Smaller font sizing",
                "C": "End-to-end encryption and integrity via SSL/TLS certificates",
                "D": "Automatic advertisement injection",
            },
            "explanation_ar": "بروتوكول HTTPS يشفر البيانات المتبادلة لمنع التنصت والتلاعب.",
            "explanation_en": "HTTPS encrypts communications using TLS to ensure privacy and data integrity.",
            "a": "C",
        },
    ],

    # ── 3. Full-Stack Developer ──────────────────────────────────────────────
    "fullstack_developer": [
        {
            "question_ar": "ما هو مجال عمل مطور الـ Full-Stack؟",
            "question_en": "What is the primary scope of a Full-Stack Developer?",
            "options_ar": {
                "A": "الواجهات الأمامية (Frontend) فقط",
                "B": "الخلفيات البرمجية (Backend) فقط",
                "C": "تطوير كل من الواجهة الأمامية والخلفية وقواعد البيانات معاً",
                "D": "تصميم الشعارات الإعلانية فقط",
            },
            "options_en": {
                "A": "Frontend user interfaces only",
                "B": "Backend server systems only",
                "C": "Both Frontend, Backend, and Database layers combined",
                "D": "Logo graphic design only",
            },
            "explanation_ar": "مطور Full-Stack يمتلك المهارات الكافية لبناء تطبيق ويب متكامل من البداية للنهاية.",
            "explanation_en": "A Full-Stack developer can engineer both client-side and server-side software.",
            "a": "C",
        },
        {
            "question_ar": "لإرسال واستقبال طلبات HTTP غير متزامنة من واجهة المستخدم نستخدم في JavaScript؟",
            "question_en": "Which API or library is standard for making asynchronous HTTP requests from the frontend?",
            "options_ar": {
                "A": "Fetch API أو Axios",
                "B": "كتابة SQL مباشرة في المتصفح",
                "C": "HTML Tag فقط",
                "D": "برنامج Photoshop",
            },
            "options_en": {
                "A": "Fetch API or Axios",
                "B": "Direct SQL execution in browser",
                "C": "Plain HTML tag only",
                "D": "Photoshop software",
            },
            "explanation_ar": "واجهة fetch أو مكتبة Axios تستخدم لطلب البيانات من الـ Backend عبر AJAX.",
            "explanation_en": "The Fetch API and Axios are standard tools for asynchronous client-server communication.",
            "a": "A",
        },
        {
            "question_ar": "ما هو المسار الصحيح المتبع لمعالجة طلب بيانات في تطبيق ويب؟",
            "question_en": "What is the correct architectural path for a standard web data request?",
            "options_ar": {
                "A": "واجهة المستخدم (Frontend) → خادم الـ Backend → قاعدة البيانات (Database)",
                "B": "قاعدة البيانات → واجهة المستخدم مباشرة → السيرفر",
                "C": "السيرفر فقط بدون واجهة أو قاعدة بيانات",
                "D": "المتصفح يقرأ مباشرة من القرص الصلب للسيرفر",
            },
            "options_en": {
                "A": "Frontend UI → Backend Server → Database",
                "B": "Database → Frontend UI directly → Backend",
                "C": "Server only without UI or database",
                "D": "Browser reads directly from server hard drive",
            },
            "explanation_ar": "الواجهة ترسل الطلب للـ Backend، الذي يتحقق منه ويستعلم من قاعدة البيانات ثم يعيد الرد.",
            "explanation_en": "The standard flow starts from the client, reaches backend middleware/handlers, queries the DB, and returns JSON.",
            "a": "A",
        },
    ],

    # ── 4. Mobile Developer ──────────────────────────────────────────────────
    "mobile_developer": [
        {
            "question_ar": "إطار العمل Flutter يعتمد على لغة البرمجة؟",
            "question_en": "Flutter framework uses which programming language?",
            "options_ar": {"A": "Dart", "B": "HTML", "C": "SQL", "D": "Bash"},
            "options_en": {"A": "Dart", "B": "HTML", "C": "SQL", "D": "Bash"},
            "explanation_ar": "فلاتر مطور من Google ويعتمد كلياً على لغة Dart.",
            "explanation_en": "Flutter is Google's UI toolkit powered by the Dart programming language.",
            "a": "A",
        },
        {
            "question_ar": "ما هي ميزة أطر العمل متعددة المنصات (مثل Flutter و React Native)؟",
            "question_en": "What is the main benefit of cross-platform frameworks like Flutter and React Native?",
            "options_ar": {
                "A": "كتابة كود واحد يعمل على نظامي Android و iOS معاً",
                "B": "تعمل بدون الحاجة لهاتف ذكي",
                "C": "تحذف قاعدة البيانات تلقائياً",
                "D": "تزيد من استهلاك البطارية بدون فائدة",
            },
            "options_en": {
                "A": "Single codebase deployment for both Android and iOS",
                "B": "Operates without requiring a smartphone",
                "C": "Automatically deletes database tables",
                "D": "Increases battery consumption with no benefit",
            },
            "explanation_ar": "تتيح تطوير تطبيقات للهاتفين بنفس الكود المشترك، مما يوفر الوقت والجهد.",
            "explanation_en": "Cross-platform frameworks allow engineers to share code across iOS and Android platforms.",
            "a": "A",
        },
        {
            "question_ar": "ما هي اللغة الرسمية والحديثة المعتمدة لتطوير تطبيقات iOS الأصلية (Native)؟",
            "question_en": "What is the modern official programming language for Native iOS development?",
            "options_ar": {"A": "Swift", "B": "CSS", "C": "PHP", "D": "Ruby"},
            "options_en": {"A": "Swift", "B": "CSS", "C": "PHP", "D": "Ruby"},
            "explanation_ar": "لغة Swift من Apple هي اللغة الأساسية والحديثة لتطوير تطبيقات iOS و macOS.",
            "explanation_en": "Swift is Apple's modern, type-safe language for iOS, iPadOS, and macOS development.",
            "a": "A",
        },
    ],

    # ── 5. Software Engineer ─────────────────────────────────────────────────
    "software_engineer": [
        {
            "question_ar": "ماذا يعني مصطلح Refactoring في هندسة البرمجيات؟",
            "question_en": "What does Code Refactoring mean in software engineering?",
            "options_ar": {
                "A": "حذف المشروع بالكامل والبدء من الصفر",
                "B": "تحسين هيكل ونقاء الكود وأدائه دون تغيير سلوكه الخارجي",
                "C": "تغيير لغة البرمجة المستخدمة فقط",
                "D": "إضافة صور وفيديوهات للموقع",
            },
            "options_en": {
                "A": "Deleting the entire codebase and restarting",
                "B": "Restructuring existing code without changing its external behavior",
                "C": "Changing the programming language only",
                "D": "Adding images and videos to the project",
            },
            "explanation_ar": "إعادة هيكلة الكود ترفع من قابليته للقراءة والصيانة وتقلل الديون التقنية.",
            "explanation_en": "Refactoring improves non-functional attributes (readability, maintainability) while preserving behavior.",
            "a": "B",
        },
        {
            "question_ar": "ما هي الفائدة الأساسية من كتابة اختبارات الوحدة (Unit Tests) للكود؟",
            "question_en": "What is the primary benefit of writing Unit Tests for your code?",
            "options_ar": {
                "A": "زيادة عدد سطور الملف فقط",
                "B": "التأكد من صحة عمل الدوال واكتشاف الأخطاء والتراجعات مبكراً",
                "C": "إبطاء سرعة تشغيل البرنامج",
                "D": "إلغاء الحاجة لقواعد البيانات",
            },
            "options_en": {
                "A": "Artificially increasing file line counts",
                "B": "Verifying individual function correctness and catching regressions early",
                "C": "Slowing down software execution",
                "D": "Eliminating the need for databases",
            },
            "explanation_ar": "اختبارات الوحدة تضمن عمل كل جزء برمجية بشكل مستقل وتمنع ظهور أخطاء جديدة عند التعديل.",
            "explanation_en": "Unit tests ensure individual units of source code perform as expected and guard against regressions.",
            "a": "B",
        },
        {
            "question_ar": "مفهوم الكبسلة (Encapsulation) في البرمجة كائنية التوجه (OOP) يهدف إلى؟",
            "question_en": "What is the primary goal of Encapsulation in Object-Oriented Programming (OOP)?",
            "options_ar": {
                "A": "إخفاء التفاصيل الداخلية وحماية حالة الكائن من التعديل العشوائي",
                "B": "حذف المتغيرات من الذاكرة",
                "C": "تحويل الكود إلى ملفات صوتية",
                "D": "جعل جميع المتغيرات عامة ومتاحة للجميع دون قيود",
            },
            "options_en": {
                "A": "Bundling data and methods while restricting direct access to internal state",
                "B": "Clearing variables from memory",
                "C": "Converting source code into audio files",
                "D": "Making all variables public without constraints",
            },
            "explanation_ar": "الكبسلة تجمع البيانات والدوال داخل الكائن وتتحكم في الوصول إليها عبر دوال getter/setter.",
            "explanation_en": "Encapsulation bundles data with methods and restricts direct external access to component internals.",
            "a": "A",
        },
    ],

    # ── 6. Security Engineer ─────────────────────────────────────────────────
    "security_engineer": [
        {
            "question_ar": "ما هو هجوم التصيد الاحتيالي (Phishing)؟",
            "question_en": "What is a Phishing attack?",
            "options_ar": {
                "A": "خداع المستخدم عبر رسائل أو روابط مزيفة لسرقة بياناته واعتماداته",
                "B": "إيقاف السيرفر بإرسال سيل هائل من الطلبات",
                "C": "تشفير الملفات ببرامج الفدية",
                "D": "تحديث نظام التشغيل تلقائياً",
            },
            "options_en": {
                "A": "Deceiving users via fake links or emails to steal sensitive credentials",
                "B": "Overwhelming a server with excessive traffic requests (DDoS)",
                "C": "Encrypting files with ransomware",
                "D": "Automatic operating system patching",
            },
            "explanation_ar": "التصيد الاحتيالي هو هندسة اجتماعية تهدف لسرقة كلمات المرور والبيانات الحساسة.",
            "explanation_en": "Phishing is social engineering where attackers impersonate trusted entities to steal credentials.",
            "a": "A",
        },
        {
            "question_ar": "ما هي الطريقة الصحيحة والآمنة لتخزين كلمات المرور في قاعدة البيانات؟",
            "question_en": "What is the secure industry standard for storing passwords in a database?",
            "options_ar": {
                "A": "تخزينها كنص عادي واضح (Plain Text)",
                "B": "تجزئتها وتشفيرها بخوارزميات تجزئة معقدة ومملحة (Salted Hash مثل bcrypt/Argon2)",
                "C": "إرسالها في ملف نصي لجميع المستخدمين",
                "D": "تخزينها داخل كود الواجهة الأمامية",
            },
            "options_en": {
                "A": "Storing them as plain readable text",
                "B": "Using secure, salted cryptographic password hashing (e.g. bcrypt, Argon2)",
                "C": "Broadcasting them in a text file to all users",
                "D": "Embedding them directly into client-side code",
            },
            "explanation_ar": "يجب تجزئة كلمات المرور باستخدام خوارزميات بطيئة ومملحة (Salted Hashing) مثل Argon2 أو bcrypt.",
            "explanation_en": "Passwords must always be hashed with unique salts using cryptographic functions like bcrypt or Argon2.",
            "a": "B",
        },
        {
            "question_ar": "ما هو مبدأ 'أقل الصلاحيات' (Principle of Least Privilege)؟",
            "question_en": "What is the Principle of Least Privilege in security architecture?",
            "options_ar": {
                "A": "منح كل مستخدم أو نظام الحد الأدنى الضروري فقط من الصلاحيات لأداء مهامه",
                "B": "منح صلاحيات المسؤول (Admin) لجميع المستخدمين",
                "C": "منع جميع المستخدمين من الدخول للنظام نهائياً",
                "D": "توزيع الصلاحيات بشكل عشوائي",
            },
            "options_en": {
                "A": "Granting users and services only the minimum permissions necessary for their tasks",
                "B": "Granting root administrator privileges to all users",
                "C": "Blocking all users from accessing the system permanently",
                "D": "Assigning random access permissions",
            },
            "explanation_ar": "مبدأ أقل الصلاحيات يقلل من الأضرار المحتملة في حال اختراق أي حساب أو خدمة.",
            "explanation_en": "Least Privilege minimizes damage from breaches by restricting access only to essential resources.",
            "a": "A",
        },
    ],

    # ── 7. Solutions Architect ───────────────────────────────────────────────
    "solutions_architect": [
        {
            "question_ar": "ما هي الوظيفة الأساسية لموزع الأحمال (Load Balancer)؟",
            "question_en": "What is the primary function of a Load Balancer?",
            "options_ar": {
                "A": "توزيع حركة المرور والطلبات بالتساوي عبر مجموعة من الخوادم لمنع الضغط",
                "B": "تعديل الصور في صفحات الموقع",
                "C": "توليد أكواد CSS تلقائياً",
                "D": "إيقاف السيرفرات عند زيادة الطلبات",
            },
            "options_en": {
                "A": "Distributing incoming network traffic evenly across a pool of backend servers",
                "B": "Resizing web image assets",
                "C": "Auto-generating CSS stylesheets",
                "D": "Shutting down servers during high load",
            },
            "explanation_ar": "موزع الأحمال يضمن استقرار الخدمة وتوافرها العالي ومنع اختناق خادم واحد.",
            "explanation_en": "Load balancers maximize throughput, minimize response times, and prevent server bottlenecks.",
            "a": "A",
        },
        {
            "question_ar": "ماذا يعني التوسع الأفقي (Horizontal Scaling / Scale Out)؟",
            "question_en": "What does Horizontal Scaling (Scale Out) mean in cloud architecture?",
            "options_ar": {
                "A": "زيادة عدد الخوادم أو الحاويات العاملة في النظام لتوزيع الحمل",
                "B": "استبدال الخادم بجهاز أغلى وزيادة الرام فقط على نفس الجهاز",
                "C": "تصغير مقاس شاشة الموقع",
                "D": "حذف قاعدة البيانات لتقليل الحجم",
            },
            "options_en": {
                "A": "Adding more server nodes or container instances to handle increased load",
                "B": "Upgrading CPU/RAM on a single machine only (Vertical Scaling)",
                "C": "Shrinking the browser viewport dimensions",
                "D": "Dropping database tables to reduce storage",
            },
            "explanation_ar": "التوسع الأفقي يضيف خوادم إضافية بالتوازي لزيادة القدرة الاستيعابية للنظام دون سقف محدد.",
            "explanation_en": "Horizontal scaling involves adding more machines to your pool of resources rather than upgrading one machine.",
            "a": "A",
        },
        {
            "question_ar": "ما هو مفهوم التوافر العالي (High Availability) في الأنظمة السحابية؟",
            "question_en": "What is High Availability (HA) in cloud systems?",
            "options_ar": {
                "A": "ضمان استمرار تشغيل النظام وعمله بدون انقطاع حتى عند فشل أحد المكونات",
                "B": "جعل الموقع مجانياً لجميع الزوار",
                "C": "توفير صور عالية الدقة فقط",
                "D": "إلغاء كلمات المرور لتسريع الدخول",
            },
            "options_en": {
                "A": "Ensuring continuous operational uptime and zero downtime even when components fail",
                "B": "Making website access completely free for all users",
                "C": "Serving only ultra-high-definition media files",
                "D": "Disabling authentication for faster logins",
            },
            "explanation_ar": "التوافر العالي يعتمد على التكرار (Redundancy) والتبديل التلقائي (Failover) لتجنب انقطاع الخدمة.",
            "explanation_en": "High availability uses redundant nodes and automated failover to eliminate single points of failure.",
            "a": "A",
        },
    ],

    # ── 8. System Architect ──────────────────────────────────────────────────
    "system_architect": [
        {
            "question_ar": "ما هي الفائدة الأساسية من تقسيم النظام إلى بنية خدمات مصغرة (Microservices)؟",
            "question_en": "What is a core benefit of a Microservices architecture?",
            "options_ar": {
                "A": "فصل المكونات والخدمات لتعمل وتُطوّر وتُنشر بشكل مستقل وقابل للتوسع",
                "B": "كتابة كل النظام في ملف واحد ضخم",
                "C": "إلغاء الحاجة لشبكات الاتصال",
                "D": "تقليل عدد المطورين في الفريق",
            },
            "options_en": {
                "A": "Decoupling services so they can be developed, scaled, and deployed independently",
                "B": "Writing the entire codebase into a single monolithic file",
                "C": "Eliminating network communication requirements",
                "D": "Mandatory reduction of engineering headcount",
            },
            "explanation_ar": "الخدمات المصغرة تتيح استقلالية التطوير والنشر وتسهيل التوسع لكل خدمة بحسب احتياجها.",
            "explanation_en": "Microservices structure an app as a collection of loosely coupled, independently deployable services.",
            "a": "A",
        },
        {
            "question_ar": "تقنية الحاويات (مثل Docker) تساعد في؟",
            "question_en": "Containerization technology (such as Docker) helps to:",
            "options_ar": {
                "A": "حزم التطبيق مع جميع مكتباته واعتمادياته ليعمل بنفس الطريقة في أي بيئة",
                "B": "تصميم واجهات المستخدم الرسومية",
                "C": "زيادة سرعة كتابة المقالات",
                "D": "إلغاء الحاجة لكتابة كود برمجي",
            },
            "options_en": {
                "A": "Package an application with all dependencies ensuring consistent execution across environments",
                "B": "Design graphic user interfaces",
                "C": "Accelerate blog post writing",
                "D": "Eliminate the need for programming code",
            },
            "explanation_ar": "الحاويات توحد بيئة التشغيل وتمنع مشكلة 'يعمل على جهازي فقط'.",
            "explanation_en": "Containers package code and dependencies together, eliminating environment drift between dev and prod.",
            "a": "A",
        },
        {
            "question_ar": "ما هو الغرض من مسارات التكامل والنشر المستمر (CI/CD Pipelines)؟",
            "question_en": "What is the primary objective of Continuous Integration and Deployment (CI/CD)?",
            "options_ar": {
                "A": "أتمتة عمليات بناء واختبار ونشر الكود لضمان الجودة والسرعة والموثوقية",
                "B": "إرسال رسائل بريد تسويقية للمستخدمين",
                "C": "كتابة كود الواجهة الأمامية تلقائياً",
                "D": "إيقاف السيرفرات في عطلات نهاية الأسبوع",
            },
            "options_en": {
                "A": "Automating code build, test, and release processes for rapid, reliable delivery",
                "B": "Sending marketing newsletter emails to customers",
                "C": "Auto-generating client-side UI templates",
                "D": "Shutting down servers during weekends",
            },
            "explanation_ar": "مسارات CI/CD تضمن فحص كل كود جديد ونشره للسيرفر بأقل تدخل بشري وأعلى موثوقية.",
            "explanation_en": "CI/CD automates testing and deployment steps to minimize manual errors and accelerate release cycles.",
            "a": "A",
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper & Extraction Functions
# ─────────────────────────────────────────────────────────────────────────────

def get_random_questions(role: str, count: int = 3) -> List[Dict[str, Any]]:
    """
    Returns `count` randomly sampled questions for a given specialization track.
    Safely handles missing or unknown roles by falling back to frontend.
    """
    bank = questions.get(role) or questions.get("frontend", [])
    if not bank:
        return []
    return random.sample(bank, min(count, len(bank)))


def get_track_info(role_key: str) -> Dict[str, str]:
    """Retrieve localized metadata for a specialization track."""
    return SPECIALIZATIONS_MAP.get(
        role_key,
        {
            "value": role_key,
            "emoji": "💻",
            "name_ar": role_key.replace("_", " ").title(),
            "name_en": role_key.replace("_", " ").title(),
            "desc_ar": "تخصص تقني معتمد في البرمجة وتطوير الأنظمة",
            "desc_en": "Certified technical track in software engineering",
        },
    )


def get_question_text(question_data: Dict[str, Any], lang: str = "ar") -> str:
    """Extract question text matching language with fallback."""
    if lang == "en":
        return str(
            question_data.get("question_en")
            or question_data.get("q_en")
            or question_data.get("question_ar")
            or question_data.get("q")
            or ""
        ).strip()
    return str(
        question_data.get("question_ar")
        or question_data.get("q_ar")
        or question_data.get("q")
        or question_data.get("question_en")
        or ""
    ).strip()


def get_options(question_data: Dict[str, Any], lang: str = "ar") -> Dict[str, str]:
    """Extract options dictionary matching language with fallback."""
    if lang == "en":
        return (
            question_data.get("options_en")
            or question_data.get("c_en")
            or question_data.get("options_ar")
            or question_data.get("c_ar")
            or question_data.get("c")
            or {}
        )
    return (
        question_data.get("options_ar")
        or question_data.get("c_ar")
        or question_data.get("c")
        or question_data.get("options_en")
        or {}
    )


def get_explanation(question_data: Dict[str, Any], lang: str = "ar") -> str:
    """Extract explanation matching language with fallback."""
    if lang == "en":
        return str(
            question_data.get("explanation_en")
            or question_data.get("explanation_ar")
            or question_data.get("explanation")
            or ""
        ).strip()
    return str(
        question_data.get("explanation_ar")
        or question_data.get("explanation")
        or question_data.get("explanation_en")
        or ""
    ).strip()
