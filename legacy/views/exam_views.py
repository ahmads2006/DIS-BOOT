"""
Exam Views — Bilingual UI components for the DM technical examination system.

Provides:
  1. ExamLandingLanguageView: Bilingual initial landing with smart default detection.
  2. ExamSelectView: Localized track selection dropdown + 'Change Language' button.
  3. QuestionView: Interactive 2x2 grid for answering A, B, C, D.
  4. ExamPanelLaunchView: Persistent channel button to trigger DM onboarding.
"""

from typing import Optional
import discord
from discord.ui import Button, Select, View

from config import EXAM_BILINGUAL_COPY
from legacy.core.exam_engine import (
    build_exam_warning_embed,
    handle_exam_timeout,
    process_answer,
    send_next_question,
    start_exam_core,
)
from legacy.core.logger import log
from legacy.core.state import active_exams
from legacy.DATA import SPECIALIZATIONS, get_track_info


# ─────────────────────────────────────────────────────────────────────────────
# Helper & Embed Builder Functions
# ─────────────────────────────────────────────────────────────────────────────

def detect_user_default_language(
    user: discord.abc.User,
    guild: Optional[discord.Guild] = None,
) -> str:
    """
    Detect suggested language for the user based on Discord roles or environment.
    Defaults to 'ar' if no explicit role is present.
    """
    roles = []
    try:
        if hasattr(user, "roles") and user.roles:
            roles = [r.name.strip().lower() for r in user.roles if hasattr(r, "name")]
        elif guild and hasattr(guild, "get_member"):
            member = guild.get_member(user.id)
            if member and hasattr(member, "roles") and member.roles:
                roles = [r.name.strip().lower() for r in member.roles if hasattr(r, "name")]
    except Exception as e:
        log.warning(f"Error detecting user language roles: {e}")
        roles = []

    has_english = any(r == "english" for r in roles)
    has_arabic = any(r == "arabic" for r in roles)

    if has_english and not has_arabic:
        return "en"
    return "ar"


def build_exam_landing_embed(suggested_lang: str = "ar") -> discord.Embed:
    """Create the bilingual initial DM landing embed."""
    suggested_label = "🇬🇧 English" if suggested_lang == "en" else "🇸🇦 العربية"
    embed = discord.Embed(
        title="🧪 نظام الاختبارات التقنية | Technical Assessment",
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🇸🇦 **مرحباً بك في نظام التقييم البرمجي المعتمد!**\n"
            "أثبت خبرتك البرمجية واحصل على رتبة مطور معتمد في السيرفر.\n"
            "يرجى اختيار لغة الاختبار المفضلة للمتابعة:\n\n"
            "🇬🇧 **Welcome to the Certified Technical Evaluation System!**\n"
            "Prove your software engineering skills and earn your verified role.\n"
            "Please select your preferred exam language to begin:\n\n"
            f"💡 **الاختيار المقترح بناءً على نشاطك / Suggested default:** `{suggested_label}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.from_rgb(88, 101, 242),
    )
    embed.set_footer(text="Programming & Dev • Bilingual Technical Certification System")
    return embed


def build_track_select_embed(lang: str = "ar") -> discord.Embed:
    """Create the localized track selection embed matching selected language."""
    copy = EXAM_BILINGUAL_COPY.get(lang, EXAM_BILINGUAL_COPY["ar"])
    embed = discord.Embed(
        title=copy["track_select_title"],
        description=copy["track_select_desc"],
        color=discord.Color.from_rgb(88, 101, 242),
    )
    footer_text = (
        "Technical Certification System • Choose your track below"
        if lang == "en"
        else "نظام الاعتماد البرمجي • اختر التخصص من القائمة أدناه"
    )
    embed.set_footer(text=footer_text)
    return embed


# ─────────────────────────────────────────────────────────────────────────────
# 1. Initial DM Landing & Language Selection View
# ─────────────────────────────────────────────────────────────────────────────

class ExamLandingLanguageView(View):
    """Initial DM landing view offering Arabic and English selection."""

    def __init__(
        self,
        bot: discord.Client,
        guild_id: int,
        suggested_lang: str = "ar",
    ) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.suggested_lang = suggested_lang

        # Highlight suggested language button as primary
        self.btn_ar.style = (
            discord.ButtonStyle.primary
            if suggested_lang == "ar"
            else discord.ButtonStyle.secondary
        )
        self.btn_en.style = (
            discord.ButtonStyle.primary
            if suggested_lang == "en"
            else discord.ButtonStyle.secondary
        )

    async def _select_lang(self, interaction: discord.Interaction, lang: str) -> None:
        embed = build_track_select_embed(lang=lang)
        view = ExamSelectView(bot=self.bot, guild_id=self.guild_id, lang=lang)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🇸🇦 العربية", row=0)
    async def btn_ar(self, interaction: discord.Interaction, button: Button) -> None:
        await self._select_lang(interaction, "ar")

    @discord.ui.button(label="🇬🇧 English", row=0)
    async def btn_en(self, interaction: discord.Interaction, button: Button) -> None:
        await self._select_lang(interaction, "en")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dynamic Track Selection View
# ─────────────────────────────────────────────────────────────────────────────

class ExamSpecialtySelect(Select):
    """Dropdown for selecting a specialization track localized in chosen language."""

    def __init__(self, bot: discord.Client, guild_id: int, lang: str = "ar") -> None:
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang
        copy = EXAM_BILINGUAL_COPY.get(lang, EXAM_BILINGUAL_COPY["ar"])

        options = [
            discord.SelectOption(
                label=spec["name_en"] if lang == "en" else spec["name_ar"],
                emoji=spec["emoji"],
                value=spec["value"],
                description=spec["desc_en"] if lang == "en" else spec["desc_ar"],
            )
            for spec in SPECIALIZATIONS
        ]

        super().__init__(
            placeholder=copy["track_select_placeholder"],
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        role_key = self.values[0]
        await interaction.response.defer()
        copy = EXAM_BILINGUAL_COPY.get(self.lang, EXAM_BILINGUAL_COPY["ar"])

        status, *extra = await start_exam_core(
            bot=self.bot,
            user=interaction.user,
            guild_id=self.guild_id,
            role_key=role_key,
            lang=self.lang,
        )

        if status == "ok":
            dm_channel = extra[0]
            self.disabled = True
            self.placeholder = copy["track_locked"]
            try:
                await interaction.edit_original_response(view=self.view)
            except Exception:
                pass

            # Deliver prominent bilingual red warning embed before Question 1
            try:
                warning_embed = build_exam_warning_embed()
                warn_msg = await dm_channel.send(embed=warning_embed)
                if interaction.user.id in active_exams:
                    active_exams[interaction.user.id]["dm_message_ids"].append(warn_msg.id)
            except Exception as e:
                log.warning(f"Could not send warning embed to {interaction.user.name}: {e}")

            await send_next_question(self.bot, interaction.user, dm_channel)
        elif status == "already_active":
            await interaction.followup.send(copy["active_exam_exists"])
        elif status == "cooldown":
            hours = extra[0]
            await interaction.followup.send(
                f"⛔ {copy['cooldown_msg']} {hours} {copy['cooldown_hours']}."
            )
        elif status == "no_questions":
            await interaction.followup.send(copy["no_questions"])
        elif status == "dm_forbidden":
            await interaction.followup.send(copy["dm_closed"])


class ChangeLanguageButton(Button):
    """Button allowing returning to the language selection menu at any time."""

    def __init__(self, bot: discord.Client, guild_id: int) -> None:
        super().__init__(
            label="🌐 تغيير اللغة / Change Language",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.bot = bot
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        suggested = detect_user_default_language(interaction.user, interaction.guild)
        embed = build_exam_landing_embed(suggested_lang=suggested)
        view = ExamLandingLanguageView(
            bot=self.bot, guild_id=self.guild_id, suggested_lang=suggested
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ExamSelectView(View):
    """Track selection view with localized select menu and Change Language button."""

    def __init__(self, bot: discord.Client, guild_id: int, lang: str = "ar") -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang

        self.add_item(ExamSpecialtySelect(bot=bot, guild_id=guild_id, lang=lang))
        self.add_item(ChangeLanguageButton(bot=bot, guild_id=guild_id))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Question Buttons View (2x2 Grid)
# ─────────────────────────────────────────────────────────────────────────────

class QuestionView(View):
    """Interactive choice buttons (A, B, C, D) arranged in a 2x2 grid."""

    def __init__(
        self,
        bot: discord.Client,
        user: discord.User,
        timeout_seconds: int = 60,
    ) -> None:
        super().__init__(timeout=timeout_seconds)
        self.bot = bot
        self.user = user
        self.answered = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def _disable_all(
        self,
        interaction: discord.Interaction,
        selected_choice: str = "",
    ) -> None:
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True
                if child.label == selected_choice:
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary
        try:
            await interaction.response.edit_message(view=self)
        except Exception:
            pass

    async def on_timeout(self) -> None:
        if not self.answered:
            for child in self.children:
                child.disabled = True
            await handle_exam_timeout(self.bot, self.user)

    async def _answer(self, interaction: discord.Interaction, choice: str) -> None:
        if self.answered:
            return
        self.answered = True
        await self._disable_all(interaction, selected_choice=choice)
        await process_answer(self.bot, self.user, choice, interaction)

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary, row=0)
    async def btn_a(self, i: discord.Interaction, b: Button) -> None:
        await self._answer(i, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary, row=0)
    async def btn_b(self, i: discord.Interaction, b: Button) -> None:
        await self._answer(i, "B")

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary, row=1)
    async def btn_c(self, i: discord.Interaction, b: Button) -> None:
        await self._answer(i, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary, row=1)
    async def btn_d(self, i: discord.Interaction, b: Button) -> None:
        await self._answer(i, "D")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Persistent Launch Button in #test-yourself
# ─────────────────────────────────────────────────────────────────────────────

class ExamPanelLaunchView(View):
    """Persistent button in test channel triggering bilingual DM onboarding."""

    def __init__(self, bot: Optional[discord.Client] = None) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="بدء الاختبار | Start Exam 🧪",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_exam_launch_btn",
        emoji="🚀",
    )
    async def launch_exam_btn(
        self,
        interaction: discord.Interaction,
        button: Button,
    ) -> None:
        if interaction.user.id in active_exams:
            await interaction.response.send_message(
                "⚠️ لديك اختبار قائم بالفعل! يرجى إكمال إجابتك في الرسائل الخاصة.\n"
                "⚠️ You already have an active exam session! Please complete your pending test in DMs.",
                ephemeral=True,
            )
            return

        bot = self.bot or interaction.client
        guild_id = interaction.guild_id or 0

        # Ephemeral confirmation in channel
        await interaction.response.send_message(
            "📩 تم إرسال لوحة الاختبار واختيار اللغة إلى **رسائلك الخاصة (DM)**.\n"
            "📩 The technical exam dashboard has been sent to your **Direct Messages (DMs)**.\n"
            "⚠️ إذا لم تصلك الرسالة، يرجى تفعيل الرسائل المباشرة في إعدادات السيرفر.",
            ephemeral=True,
        )

        try:
            dm = await interaction.user.create_dm()
            suggested = detect_user_default_language(
                interaction.user, interaction.guild
            )
            landing_embed = build_exam_landing_embed(suggested_lang=suggested)
            view = ExamLandingLanguageView(
                bot=bot, guild_id=guild_id, suggested_lang=suggested
            )
            await dm.send(embed=landing_embed, view=view)
        except discord.Forbidden:
            try:
                await interaction.followup.send(
                    "❌ لا يمكن للبوت إرسال رسائل في الخاص لديك!\n"
                    "❌ I cannot send you direct messages.\n"
                    "📌 **يرجى فتح الرسائل الخاصة (Direct Messages) في إعدادات الخصوصية ثم المحاولة مجدداً.**",
                    ephemeral=True,
                )
            except Exception:
                pass
