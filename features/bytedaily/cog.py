"""
ByteDaily Cog — Discord extension entry point.

This Cog is loaded by main.py via bot.load_extension('features.bytedaily.cog').
It is responsible for:
  - Registering public and admin slash commands (/leaderboard, /bytedaily-post, /bytedaily-close, /bytedaily-add-question, /bytedaily-status, /bytedaily-generate-ai)
  - Starting the ByteDaily scheduler loop on cog_load
  - Stopping the scheduler loop on cog_unload
  - Initializing the ByteDaily database pool on cog_load
  - Closing the ByteDaily database pool on cog_unload

The cog delegates business logic to services/ and database repositories.
"""

from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

from bridge.legacy_adapter import log
from features.shared.embed_helpers import (
    make_info_embed,
    make_error_embed,
    make_success_embed,
)
from .constants import BD_CHANNEL_ID, BD_LEADERBOARD_CHANNEL_ID
from .database.client import bd_db
from .database.repositories import question_repo, user_repo
from .scheduler import ByteDailyScheduler
from .services import poll_service, question_service, stats_service, ai_generator_service, leaderboard_service


class ByteDailyCog(commands.Cog, name="ByteDaily"):
    """ByteDaily feature extension cog."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.scheduler = ByteDailyScheduler(bot)

    async def cog_load(self) -> None:
        """Register button handlers first, then DB + scheduler."""
        log.info("ByteDaily: Loading cog — registering DynamicItems before DB init...")
        # CRITICAL: register handlers before any await that can delay readiness,
        # otherwise Discord button clicks expire with "didn't respond in time".
        self.scheduler.register_dynamic_items()

        log.info("ByteDaily: Initializing database pool and starting cycle...")
        await bd_db.initialize()
        self.scheduler.start()
        log.info("ByteDaily: Cog load complete.")

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Ensure slash-command failures still get an ephemeral reply."""
        log.error(f"ByteDaily slash command error: {error}", exc_info=True)
        try:
            # Prefer defer + followup; only use response.send_message if never deferred
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ", f"فشل تنفيذ الأمر: {error}"),
                ephemeral=True,
            )
        except Exception:
            pass

    async def cog_unload(self) -> None:
        """Stop scheduler loop and close DB pool on extension unload."""
        log.info("ByteDaily: Unloading cog — stopping scheduler and closing database pool...")
        self.scheduler.stop()
        await bd_db.close()
        log.info("ByteDaily: Cog unload complete.")

    # ─────────────────────────────────────────────────────────────────────────
    # Public Slash Commands
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="leaderboard",
        description="عرض قائمة المتصدرين وأعلى النقاط / View ByteDaily Leaderboard",
    )
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        """
        Public command: refresh the single static #leaderboard message in-place,
        then show an ephemeral snapshot (never posts a duplicate in the channel).
        """
        await interaction.response.defer(ephemeral=True)
        try:
            # Keep the pinned #leaderboard message as the single source of truth
            await leaderboard_service.refresh_leaderboard_embed(self.bot)

            top_users = await user_repo.get_leaderboard(limit=10)
            embed = leaderboard_service.build_leaderboard_embed(top_users)

            lb_channel = self.bot.get_channel(BD_LEADERBOARD_CHANNEL_ID) if BD_LEADERBOARD_CHANNEL_ID else None
            channel_hint = (
                f"\n📌 اللوحة المباشرة • Live Board: {lb_channel.mention}"
                if lb_channel
                else (
                    f"\n📌 اللوحة المباشرة • Live Board: <#{BD_LEADERBOARD_CHANNEL_ID}>"
                    if BD_LEADERBOARD_CHANNEL_ID
                    else ""
                )
            )
            if channel_hint:
                embed.description = (embed.description or "") + channel_hint

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.error(f"ByteDaily: /leaderboard error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ / Error", f"فشل جلب لوحة المتصدرين / Failed to fetch leaderboard: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-language",
        description="تغيير لغة التحديات والشروحات المفضلة / Set preferred ByteDaily language",
    )
    @app_commands.choices(
        language=[
            app_commands.Choice(name="العربية (Arabic)", value="ar"),
            app_commands.Choice(name="English (الإنجليزية)", value="en"),
            app_commands.Choice(name="تلقائي حسب الرتبة (Auto / Detect from Role)", value="auto"),
        ]
    )
    async def bytedaily_language(
        self,
        interaction: discord.Interaction,
        language: app_commands.Choice[str],
    ) -> None:
        """Public command: Set user preferred language for ByteDaily."""
        await interaction.response.defer(ephemeral=True)
        try:
            val = None if language.value == "auto" else language.value
            await user_repo.set_preferred_language(interaction.user.id, val)
            if language.value == "en":
                msg = "🌐 Preferred language set to **English**! Challenge responses and explanations will now appear in English."
            elif language.value == "ar":
                msg = "🌐 تم ضبط لغتك المفضلة إلى **العربية**! ستظهر إشعارات التحديات والشروحات باللغة العربية."
            else:
                msg = "🌐 تم ضبط اللغة إلى **تلقائي (حسب رتبتك في السيرفر)**! Language will be auto-detected from your server role (English / Arabic)."
            await interaction.followup.send(
                embed=make_success_embed("Language Updated / تم تغيير اللغة", msg),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: /bytedaily-language error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("Error", f"Failed to set language: {e}"),
                ephemeral=True,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Admin Slash Commands
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="bytedaily-post",
        description="[أدمن] نشر تحدي ByteDaily جديد في القناة فوراً / [Admin] Post new challenge immediately",
    )
    @app_commands.default_permissions(administrator=True)
    async def bytedaily_post(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Admin command: Post a new question immediately."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        open_poll = await poll_service.get_open_poll()
        if open_poll:
            await interaction.followup.send(
                embed=make_error_embed(
                    "تحدٍّ نشط بالفعل • Poll Already Open",
                    f"يوجد تحدي نشط بالفعل (**#{open_poll['id']}**). يرجى إغلاقه أولاً قبل طرح تحدٍّ جديد.\n"
                    f"There is already an active poll (**#{open_poll['id']}**). Close it first before posting a new one.",
                ),
                ephemeral=True,
            )
            return

        # Resolve target channel: parameter > default BD_CHANNEL_ID
        target_channel = channel or (self.bot.get_channel(BD_CHANNEL_ID) if BD_CHANNEL_ID else None)
        if not target_channel:
            await interaction.followup.send(
                embed=make_error_embed(
                    "لم يتم العثور على القناة • Target Channel Not Found",
                    "تعذر العثور على القناة المحددة. يرجى ضبط BD_CHANNEL_ID أو تحديد قناة صالحة.\n"
                    "Target channel not found. Please set BD_CHANNEL_ID or specify a channel parameter.",
                ),
                ephemeral=True,
            )
            return

        try:
            await self.scheduler._post_question(target_channel=target_channel)
            open_poll = await poll_service.get_open_poll()
            poll_id_str = f"#{open_poll['id']}" if open_poll else "new"
            await interaction.followup.send(
                embed=make_success_embed(
                    "تم نشر التحدي • Challenge Posted",
                    f"تم نشر تحدي ByteDaily بنجاح ({poll_id_str}) في {target_channel.mention}!\n"
                    f"Successfully posted a new ByteDaily challenge ({poll_id_str}) to {target_channel.mention}!",
                ),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: Error posting challenge manually: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في النشر • Posting Error", f"فشل نشر التحدي / Failed to post challenge: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-close",
        description="[أدمن] إغلاق التحدي النشط وحساب النتائج / [Admin] Close active challenge and compute results",
    )
    @app_commands.default_permissions(administrator=True)
    async def bytedaily_close(self, interaction: discord.Interaction) -> None:
        """Admin command: Close active poll immediately."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        open_poll = await poll_service.get_open_poll()
        if not open_poll:
            await interaction.followup.send(
                embed=make_error_embed(
                    "لا يوجد تحدٍّ نشط • No Open Poll",
                    "لا يوجد استبيان نشط حالياً لإغلاقه. / There is no currently active ByteDaily poll to close.",
                ),
                ephemeral=True,
            )
            return

        try:
            poll_id = open_poll['id']
            await self.scheduler._close_poll(poll_id)
            await interaction.followup.send(
                embed=make_success_embed(
                    "تم إغلاق التحدي • Poll Closed",
                    f"تم إغلاق التحدي **#{poll_id}** واحتساب النتائج والسلاسل بنجاح!\n"
                    f"Successfully closed ByteDaily poll **#{poll_id}** and calculated results!",
                ),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: Error closing poll manually: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في الإغلاق • Close Error", f"فشل إغلاق التحدي / Failed to close poll: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-force-cycle",
        description="[أدمن] فرض دورة كاملة: إغلاق، نتائج، لوحة، وتحدٍّ جديد / [Admin] Force full challenge cycle",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        reset_leaderboard_points="إن كان True يتم تصفير نقاط وstreaks جميع الأعضاء / Reset all points & streaks if True",
    )
    async def bytedaily_force_cycle(
        self,
        interaction: discord.Interaction,
        reset_leaderboard_points: bool = False,
    ) -> None:
        """Admin command: Force-advance the full ByteDaily cycle in one action."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        if not BD_CHANNEL_ID:
            await interaction.followup.send(
                embed=make_error_embed(
                    "الإعداد غير مكتمل • Not Configured",
                    "لم يتم ضبط `BD_CHANNEL_ID` في ملف `.env`. / BD_CHANNEL_ID is not set in `.env`.",
                ),
                ephemeral=True,
            )
            return

        # Immediate ack so Discord never times out during the long cycle work
        await interaction.followup.send(
            "⏳ جاري فرض الدورة الكاملة (إغلاق → نتائج → لوحة → تحدٍّ جديد)…\n"
            "⏳ Forcing complete cycle (close → results → leaderboard → new challenge)…",
            ephemeral=True,
        )

        try:
            summary = await self.scheduler.force_cycle(
                reset_leaderboard_points=reset_leaderboard_points,
            )
            detail_bits = []
            if summary.get("closed_poll_id"):
                detail_bits.append(f"أُغلق التحدي **#{summary['closed_poll_id']}** • Closed poll #{summary['closed_poll_id']}")
            if summary.get("new_poll_id"):
                detail_bits.append(f"التحدي الجديد **#{summary['new_poll_id']}** • New poll #{summary['new_poll_id']}")
            if summary.get("points_reset"):
                detail_bits.append(f"تم تصفير نقاط {summary.get('users_reset', 0)} مشارك • Points reset for {summary.get('users_reset', 0)} users")

            detail = ("\n".join(detail_bits) + "\n") if detail_bits else ""
            await interaction.followup.send(
                embed=make_success_embed(
                    "اكتملت الدورة الإجبارية • Force Cycle Complete",
                    "🔄 تم فرض دورة جديدة بنجاح! تم إغلاق التحدي السابق، نشر النتائج، "
                    "تحديث لوحة الصدارة، وطرح التحدي الجديد.\n"
                    "Successfully advanced full cycle (previous closed, results posted, leaderboard updated, new challenge posted).\n\n"
                    f"{detail}",
                ),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: /bytedaily-force-cycle error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في الدورة • Force Cycle Error", f"فشل فرض الدورة / Failed to force cycle: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-extend",
        description="[أدمن] تمديد مدة التحدي النشط حالياً / [Admin] Extend active challenge duration",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        hours="عدد الساعات المراد إضافتها / Hours to add",
        minutes="عدد الدقائق المراد إضافتها (اختياري) / Minutes to add (optional)",
    )
    async def bytedaily_extend(
        self,
        interaction: discord.Interaction,
        hours: int,
        minutes: int = 0,
    ) -> None:
        """Admin command: Extend the active challenge duration."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        total_minutes = hours * 60 + minutes
        if hours < 0 or minutes < 0 or total_minutes <= 0:
            await interaction.followup.send(
                embed=make_error_embed(
                    "قيمة غير صالحة • Invalid Value",
                    "يجب تحديد مدة تمديد موجبة (ساعات و/أو دقائق أكبر من صفر).\n"
                    "Must specify a positive duration (hours and/or minutes greater than 0).",
                ),
                ephemeral=True,
            )
            return

        open_poll = await poll_service.get_open_poll()
        if not open_poll:
            await interaction.followup.send(
                embed=make_error_embed(
                    "لا يوجد تحدٍّ نشط • No Active Poll",
                    "لا يوجد تحدي ByteDaily مفتوح حالياً لتمديده.\n"
                    "There is no currently active ByteDaily poll to extend.",
                ),
                ephemeral=True,
            )
            return

        try:
            result = await poll_service.modify_poll_duration(
                self.bot,
                poll_id=open_poll["id"],
                minutes_delta=total_minutes,
            )
            self.scheduler.nudge()
            unix = result["ends_at_unix"]
            await interaction.followup.send(
                f"✅ تم تمديد وقت التحدي بنجاح! ينتهي الآن • Challenge extended! Ends at: <t:{unix}:F> (<t:{unix}:R>)",
                ephemeral=True,
            )
        except poll_service.PollDurationError as e:
            await interaction.followup.send(
                embed=make_error_embed("تمديد غير صالح • Invalid Extension", str(e)),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: /bytedaily-extend error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في التمديد • Extend Error", f"فشل تمديد وقت التحدي / Failed to extend poll: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-reduce",
        description="[أدمن] تقليص الوقت المتبقي للتحدي النشط / [Admin] Reduce active challenge duration",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        hours="عدد الساعات المراد خصمها / Hours to reduce",
        minutes="عدد الدقائق المراد خصمها (اختياري) / Minutes to reduce (optional)",
    )
    async def bytedaily_reduce(
        self,
        interaction: discord.Interaction,
        hours: int,
        minutes: int = 0,
    ) -> None:
        """Admin command: Reduce the active challenge remaining duration."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        total_minutes = hours * 60 + minutes
        if hours < 0 or minutes < 0 or total_minutes <= 0:
            await interaction.followup.send(
                embed=make_error_embed(
                    "قيمة غير صالحة • Invalid Value",
                    "يجب تحديد مدة تقليص موجبة (ساعات و/أو دقائق أكبر من صفر).\n"
                    "Must specify a positive reduction (hours and/or minutes greater than 0).",
                ),
                ephemeral=True,
            )
            return

        open_poll = await poll_service.get_open_poll()
        if not open_poll:
            await interaction.followup.send(
                embed=make_error_embed(
                    "لا يوجد تحدٍّ نشط • No Active Poll",
                    "لا يوجد تحدي ByteDaily مفتوح حالياً لتقليص وقته.\n"
                    "There is no currently active ByteDaily poll to reduce.",
                ),
                ephemeral=True,
            )
            return

        try:
            result = await poll_service.modify_poll_duration(
                self.bot,
                poll_id=open_poll["id"],
                minutes_delta=-total_minutes,
            )
            self.scheduler.nudge()
            unix = result["ends_at_unix"]
            await interaction.followup.send(
                f"⏱️ تم تقليص وقت التحدي! ينتهي الآن • Challenge reduced! Ends at: <t:{unix}:F> (<t:{unix}:R>)",
                ephemeral=True,
            )
        except poll_service.PollDurationError as e:
            await interaction.followup.send(
                embed=make_error_embed("تقليص غير صالح • Invalid Reduction", str(e)),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: /bytedaily-reduce error: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في التقليص • Reduce Error", f"فشل تقليص وقت التحدي / Failed to reduce poll: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-add-question",
        description="[أدمن] إضافة سؤال جديد يدوياً باللغتين لبنك الأسئلة / [Admin] Add bilingual question to bank",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        question_text="نص السؤال بالعربية (مطلوب)",
        choice_a="الخيار A بالعربية (مطلوب)",
        choice_b="الخيار B بالعربية (مطلوب)",
        choice_c="الخيار C بالعربية (مطلوب)",
        choice_d="الخيار D بالعربية (مطلوب)",
        correct_choice="حرف الإجابة الصحيحة",
        question_en="نص السؤال بالإنجليزية (مطلوب / English Question)",
        choice_a_en="الخيار A بالإنجليزية (مطلوب / English Choice A)",
        choice_b_en="الخيار B بالإنجليزية (مطلوب / English Choice B)",
        choice_c_en="الخيار C بالإنجليزية (مطلوب / English Choice C)",
        choice_d_en="الخيار D بالإنجليزية (مطلوب / English Choice D)",
        explanation="شرح الجواب بالعربية (اختياري)",
        explanation_en="شرح الجواب بالإنجليزية (اختياري / English Explanation)",
        category="التصنيف (اختياري مثل: Python, SQL, Docker)",
    )
    @app_commands.choices(
        correct_choice=[
            app_commands.Choice(name="A", value="A"),
            app_commands.Choice(name="B", value="B"),
            app_commands.Choice(name="C", value="C"),
            app_commands.Choice(name="D", value="D"),
        ]
    )
    async def bytedaily_add_question(
        self,
        interaction: discord.Interaction,
        question_text: str,
        choice_a: str,
        choice_b: str,
        choice_c: str,
        choice_d: str,
        correct_choice: app_commands.Choice[str],
        question_en: str,
        choice_a_en: str,
        choice_b_en: str,
        choice_c_en: str,
        choice_d_en: str,
        explanation: str = "",
        explanation_en: str = "",
        category: str = "",
    ) -> None:
        """Admin command: Add question to bank with mandatory dual-language fields."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        # Validation: Ensure non-empty Arabic fields
        if not (question_text.strip() and choice_a.strip() and choice_b.strip() and choice_c.strip() and choice_d.strip()):
            await interaction.followup.send(
                embed=make_error_embed(
                    "بيانات غير مكتملة • Missing Arabic Fields",
                    "يجب إدخال نص السؤال وجميع الخيارات الأربعة (A, B, C, D) باللغة العربية.\n"
                    "Arabic question and all 4 choices must not be empty.",
                ),
                ephemeral=True,
            )
            return

        # Validation: Ensure non-empty English fields
        if not (question_en.strip() and choice_a_en.strip() and choice_b_en.strip() and choice_c_en.strip() and choice_d_en.strip()):
            await interaction.followup.send(
                embed=make_error_embed(
                    "بيانات غير مكتملة • Missing English Fields",
                    "يجب إدخال نص السؤال وجميع الخيارات الأربعة (A, B, C, D) باللغة الإنجليزية.\n"
                    "English question and all 4 choices must not be empty.",
                ),
                ephemeral=True,
            )
            return

        try:
            tags = [category.strip()] if category and category.strip() else []
            options_en = {
                "A": choice_a_en.strip(),
                "B": choice_b_en.strip(),
                "C": choice_c_en.strip(),
                "D": choice_d_en.strip(),
            }

            new_id = await question_repo.insert(
                question_text=question_text.strip(),
                choice_a=choice_a.strip(),
                choice_b=choice_b.strip(),
                choice_c=choice_c.strip(),
                choice_d=choice_d.strip(),
                correct_answer=correct_choice.value,
                explanation=explanation.strip(),
                difficulty=1,
                tags=tags,
                question_en=question_en.strip(),
                options_en=options_en,
                choice_a_en=choice_a_en.strip(),
                choice_b_en=choice_b_en.strip(),
                choice_c_en=choice_c_en.strip(),
                choice_d_en=choice_d_en.strip(),
                explanation_en=explanation_en.strip() if explanation_en.strip() else None,
            )
            embed = make_success_embed(
                "تمت إضافة السؤال الثنائي • Bilingual Question Added",
                f"تمت إضافة السؤال **#{new_id}** بنجاح إلى `bd_questions` باللغتين العربية والإنجليزية!\n"
                f"Successfully added bilingual question **#{new_id}** to `bd_questions`!",
            )
            embed.add_field(name="السؤال • Question (AR)", value=question_text.strip(), inline=False)
            embed.add_field(name="السؤال • Question (EN)", value=question_en.strip(), inline=False)
            embed.add_field(name="الإجابة الصحيحة • Correct Answer", value=f"Option [{correct_choice.value}]", inline=True)
            if category:
                embed.add_field(name="التصنيف • Category", value=category.strip(), inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.error(f"ByteDaily: Error adding question: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في الإضافة • Add Error", f"فشل إضافة السؤال / Failed to add question: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-status",
        description="[أدمن] عرض حالة نظام ByteDaily والإحصائيات / [Admin] View ByteDaily system status",
    )
    @app_commands.default_permissions(administrator=True)
    async def bytedaily_status(self, interaction: discord.Interaction) -> None:
        """Admin command: View ByteDaily status."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        try:
            open_poll = await poll_service.get_open_poll()
            closed_poll = await poll_service.get_closed_poll()
            active_questions = await question_repo.get_active_questions()
            total_users = await user_repo.get_total_users()

            status_embed = make_info_embed(
                title="⚙️ حالة نظام ByteDaily • ByteDaily System Status",
                description="الحالة الحالية لقاعدة البيانات ومجدول المهام.\n"
                            "Current state of ByteDaily database and scheduler.",
            )

            channel_mention = f"<#{BD_CHANNEL_ID}>" if BD_CHANNEL_ID else "⚠️ غير مضبوط • Not Configured"
            status_embed.add_field(name="القناة المستهدفة • Target Channel", value=channel_mention, inline=False)

            if open_poll:
                opened_at = open_poll.get("opened_at", "N/A")
                poll_info = f"**Open Poll #{open_poll['id']}** (Opened: {opened_at})"
            elif closed_poll:
                closed_at = closed_poll.get("closed_at", "N/A")
                poll_info = f"**Closed Poll #{closed_poll['id']}** (Awaiting Cleanup, Closed: {closed_at})"
            else:
                poll_info = "لا يوجد استبيان نشط حالياً (خامل) • No Active Poll (Idle)"

            status_embed.add_field(name="حالة الاستبيان النشط • Active Poll State", value=poll_info, inline=False)
            status_embed.add_field(name="حجم بنك الأسئلة • Question Bank Size", value=f"{len(active_questions)} questions", inline=True)
            status_embed.add_field(name="عدد المستخدمين المسجلين • Registered Users", value=f"{total_users} users", inline=True)

            await interaction.followup.send(embed=status_embed, ephemeral=True)
        except Exception as e:
            log.error(f"ByteDaily: Error fetching status: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في الحالة • Status Error", f"فشل جلب حالة النظام / Failed to fetch status: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-generate",
        description="[أدمن] توليد أسئلة بالذكاء الاصطناعي لبنك الأسئلة / [Admin] Generate questions via AI",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(count="عدد الأسئلة المطلوب توليدها (1-10) / Number of questions to generate (1-10)")
    async def bytedaily_generate(
        self,
        interaction: discord.Interaction,
        count: int = 5,
    ) -> None:
        """Admin command: On-demand AI question generation via Gemini."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        count = max(1, min(count, 10))  # clamp to [1, 10]

        try:
            inserted = await ai_generator_service.generate_and_store_questions(count=count)
            if inserted:
                embed = make_success_embed(
                    "اكتمل التوليد بالذكاء الاصطناعي • AI Generation Complete",
                    f"✅ تم توليد وتخزين **{inserted}** سؤالاً بنجاح في `bd_questions` عبر Gemini!\n"
                    f"Successfully generated and stored **{inserted}** question(s) into `bd_questions` via Gemini!",
                )
                embed.add_field(name="المطلوب • Requested", value=str(count), inline=True)
                embed.add_field(name="تمت إضافتها • Inserted", value=str(inserted), inline=True)
            else:
                embed = make_error_embed(
                    "فشل التوليد • Generation Failed",
                    "لم يُرجع Gemini أي أسئلة صالحة. يرجى التحقق من `GEMINI_API_KEY` والحصص المتاحة.\n"
                    "Gemini returned 0 valid questions. Check GEMINI_API_KEY and API quota.",
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.error(f"ByteDaily: Error in /bytedaily-generate: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في التوليد • Generation Error", f"حدث خطأ غير متوقع / An unexpected error occurred: `{e}`"),
                ephemeral=True,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Live Leaderboard & Personal Rank
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="bytedaily-leaderboard",
        description="[أدمن] تحديث لوحة المتصدرين الثابتة فوراً / [Admin] Refresh live leaderboard message",
    )
    @app_commands.default_permissions(administrator=True)
    async def bytedaily_leaderboard_refresh(self, interaction: discord.Interaction) -> None:
        """Admin command: Force an immediate leaderboard embed refresh."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=make_error_embed(
                    "غير مصرح • Permission Denied",
                    "هذا الأمر مخصص للمسؤولين فقط. / Only administrators can run this command.",
                ),
                ephemeral=True,
            )
            return

        if not BD_LEADERBOARD_CHANNEL_ID:
            await interaction.followup.send(
                embed=make_error_embed(
                    "الإعداد غير مكتمل • Not Configured",
                    "لم يتم ضبط `BD_LEADERBOARD_CHANNEL_ID` في ملف `.env`.\n"
                    "BD_LEADERBOARD_CHANNEL_ID is not set in `.env`.",
                ),
                ephemeral=True,
            )
            return

        try:
            await leaderboard_service.refresh_leaderboard_embed(self.bot)
            lb_channel = self.bot.get_channel(BD_LEADERBOARD_CHANNEL_ID)
            channel_mention = lb_channel.mention if lb_channel else f"<#{BD_LEADERBOARD_CHANNEL_ID}>"
            await interaction.followup.send(
                embed=make_success_embed(
                    "تم تحديث اللوحة • Leaderboard Refreshed",
                    f"✅ تم تحديث لوحة المتصدرين المباشرة في {channel_mention} بنجاح!\n"
                    f"Live leaderboard has been updated in {channel_mention}.",
                ),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"ByteDaily: Error refreshing leaderboard: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ في التحديث • Refresh Error", f"فشل تحديث اللوحة / Failed to refresh leaderboard: {e}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="bytedaily-rank",
        description="عرض إحصائياتك ورتبتك / View your personal ByteDaily rank and stats",
    )
    async def bytedaily_rank(self, interaction: discord.Interaction) -> None:
        """Public command: Show the caller's personal ByteDaily stats card."""
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        try:
            stats = await user_repo.get_by_id(user_id)
            if not stats:
                await interaction.followup.send(
                    embed=make_info_embed(
                        title="📊 بياناتك في ByteDaily | Your ByteDaily Profile",
                        description=(
                            "لم تشارك في أي تحدٍّ بعد!\n"
                            "You haven't participated in any challenges yet!\n\n"
                            "حل التحدي اليومي للبدء في تجميع النقاط والترتيب. 🚀\n"
                            "Solve the daily challenge to start earning points and climb the ranks. 🚀"
                        ),
                    ),
                    ephemeral=True,
                )
                return

            rank = await user_repo.get_rank(user_id)
            total_users = await user_repo.get_total_users()

            correct = int(stats.get("correct_count", 0))
            wrong = int(stats.get("wrong_count", 0))
            total_ans = correct + wrong
            accuracy = f"{round(correct / total_ans * 100)}%" if total_ans > 0 else "—"
            current_streak = stats.get("current_streak", 0)
            best_streak = stats.get("best_streak", 0)
            points = stats.get("total_points", 0)
            rank_str = f"#{rank}" if rank else "—"

            embed = discord.Embed(
                title=f"📊 إحصائياتك في ByteDaily | Your ByteDaily Stats",
                color=discord.Color.blurple(),
            )
            embed.set_author(
                name=str(interaction.user),
                icon_url=interaction.user.display_avatar.url,
            )
            embed.add_field(
                name="🏅 الترتيب • Rank",
                value=f"**{rank_str}** / {total_users} (مشارك • participants)",
                inline=True,
            )
            embed.add_field(
                name="⭐ النقاط • Points",
                value=f"**{points}** pts",
                inline=True,
            )
            embed.add_field(
                name="🔥 السلسلة • Streak (Current/Best)",
                value=f"**{current_streak}** / **{best_streak}**",
                inline=True,
            )
            embed.add_field(
                name="✅ إجابات صحيحة • Correct",
                value=f"**{correct}** / {total_ans}",
                inline=True,
            )
            embed.add_field(
                name="🎯 نسبة الدقة • Accuracy",
                value=accuracy,
                inline=True,
            )
            embed.add_field(
                name="❌ إجابات خاطئة • Incorrect",
                value=str(wrong),
                inline=True,
            )
            embed.set_footer(text="حل التحدي اليومي لتحسين ترتيبك! • Solve daily challenges to climb the ranks!")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            log.error(f"ByteDaily: /bytedaily-rank error for user {user_id}: {e}", exc_info=True)
            await interaction.followup.send(
                embed=make_error_embed("خطأ • Error", f"فشل جلب إحصائياتك / Failed to fetch stats: {e}"),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Entry point for bot.load_extension('features.bytedaily.cog')."""
    await bot.add_cog(ByteDailyCog(bot))
