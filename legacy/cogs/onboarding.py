"""
Onboarding Cog — Automatically sends bilingual onboarding flow when members accept rules.
"""

import discord
from discord.ext import commands

from config import RULES_ACCEPTED_ROLE_NAMES
from legacy.core.logger import log
from legacy.core.state import onboarding_sent_to
from legacy.views.onboarding_views import LanguageSelectView


class OnboardingCog(commands.Cog, name="Onboarding"):
    """Handles automatic member onboarding triggers."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _has_rules_role(self, member: discord.Member) -> bool:
        member_roles = {r.name for r in member.roles}
        if any(name in member_roles for name in RULES_ACCEPTED_ROLE_NAMES):
            return True
        lower_roles = {r.name.lower() for r in member.roles}
        return any("member" in lr or "rules" in lr or "intern" in lr for lr in lower_roles)


    async def _send_onboarding(self, member: discord.Member) -> bool:
        if member.id in onboarding_sent_to:
            return False

        try:
            dm = await member.create_dm()
            view = LanguageSelectView(bot=self.bot, guild_id=member.guild.id)
            embed = discord.Embed(
                title="🌟 مرحباً بك في مجتمع المطورين! | Welcome to Dev Community!",
                description=(
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🇸🇦 **يسعدنا انضمامك إلينا!**\n"
                    "يرجى اختيار لغتك المفضلة لبدء تخصيص حسابك واختيار مسارك البرمجي:\n\n"
                    "🇬🇧 **We are thrilled to have you here!**\n"
                    "Please select your preferred language to customize your profile and select your track:\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.from_rgb(88, 101, 242),
            )
            embed.set_footer(text="Programming & Dev Community • Onboarding")
            await dm.send(embed=embed, view=view)
            onboarding_sent_to.add(member.id)
            log.info(f"Sent onboarding DM to {member.name} ({member.id})")
            return True
        except discord.Forbidden:
            log.warning(f"Could not send DM to {member.name} (DMs closed)")
            return False
        except Exception as e:
            log.error(f"Error sending onboarding to {member.name}: {e}")
            return False

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """Send onboarding interface when rules accepted role is assigned."""
        before_roles = {r.name for r in before.roles}
        after_roles = {r.name for r in after.roles}

        new_roles = [
            r
            for r in RULES_ACCEPTED_ROLE_NAMES
            if r in after_roles and r not in before_roles
        ]
        if new_roles:
            log.info(f"Member {after.name} accepted rules (Role: {new_roles[0]})")
            await self._send_onboarding(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Check member on join if they already hold accepted role."""
        if self._has_rules_role(member):
            await self._send_onboarding(member)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnboardingCog(bot))
