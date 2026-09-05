import discord
from discord.ext import commands
from config import RULES_ACCEPTED_ROLE_NAMES, ONBOARDING_INITIAL_PROMPT
from core.state import onboarding_sent_to
from core.logger import log
from views.onboarding_views import LanguageSelectView

class OnboardingCog(commands.Cog, name="Onboarding"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_rules_role(self, member: discord.Member) -> bool:
        member_roles = {r.name for r in member.roles}
        return any(name in member_roles for name in RULES_ACCEPTED_ROLE_NAMES)

    async def _send_onboarding(self, member: discord.Member) -> bool:
        if member.id in onboarding_sent_to:
            return False

        try:
            dm = await member.create_dm()
            view = LanguageSelectView(bot=self.bot, guild_id=member.guild.id)
            await dm.send(ONBOARDING_INITIAL_PROMPT, view=view)
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
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """إرسال واجهة التأهيل عند منح رتبة قبول القوانين"""
        before_roles = {r.name for r in before.roles}
        after_roles = {r.name for r in after.roles}

        new_roles = [r for r in RULES_ACCEPTED_ROLE_NAMES if r in after_roles and r not in before_roles]
        if new_roles:
            log.info(f"Member {after.name} accepted rules (Role: {new_roles[0]})")
            await self._send_onboarding(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """فحص العضو عند الانضمام إذا كان يحمل رتبة القبول مسبقاً"""
        if self._has_rules_role(member):
            await self._send_onboarding(member)

async def setup(bot: commands.Bot):
    await bot.add_cog(OnboardingCog(bot))
