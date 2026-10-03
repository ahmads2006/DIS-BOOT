import asyncio
import os
import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID
from legacy.core.logger import log
from legacy.core.database import db
from legacy.api.server import AsyncAPIServer

intents = discord.Intents.all()

class DeveloperBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.api_server = None

    async def setup_hook(self):
        log.info("Starting bot initialization...")

        # ── 1. Legacy database ──
        await db.initialize()

        # ── 2–5. Legacy cogs ──
        legacy_extensions = [
            "legacy.cogs.onboarding",
            "legacy.cogs.exam",
            "legacy.cogs.admin",
            "legacy.cogs.stats",
        ]
        for ext in legacy_extensions:
            try:
                await self.load_extension(ext)
                log.info(f"Loaded extension: {ext}")
            except Exception as e:
                log.error(f"Failed to load extension {ext}: {e}")

        # ── 6. ByteDaily cog ──
        # BD database pool and scheduler are initialized inside cog_load()
        try:
            await self.load_extension("features.bytedaily.cog")
            log.info("Loaded extension: features.bytedaily.cog")
        except Exception as e:
            log.error(f"Failed to load ByteDaily extension: {e}")

        # ── 7. Slash command sync (AFTER all extensions) ──
        try:
            if GUILD_ID:
                guild_obj = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                log.info(f"Synced {len(synced)} slash commands to Guild ID: {GUILD_ID}")
            else:
                synced = await self.tree.sync()
                log.info(f"Synced {len(synced)} global slash commands.")
        except Exception as e:
            log.error(f"Error syncing slash commands: {e}")

        # ── 8. Legacy persistent views ──
        from legacy.views.exam_views import ExamPanelLaunchView
        self.add_view(ExamPanelLaunchView(self))
        log.info("Registered Persistent ExamPanelLaunchView.")

        # ── 9. ByteDaily persistent views ──
        # DynamicItem classes (DynamicAnswerButton, DynamicResultButton) are
        # registered globally via bot.add_dynamic_items() inside scheduler.start(),
        # which is called during ByteDailyCog.cog_load(). No additional
        # bot.add_view() registration is needed — DynamicItem pattern matching
        # handles button persistence across restarts automatically.
        log.info("ByteDaily persistent views: DynamicItems registered via scheduler.")

        # ── 10. API server ──
        self.api_server = AsyncAPIServer(self)
        await self.api_server.start()

    async def close(self):
        if self.api_server:
            await self.api_server.stop()
        await super().close()


bot = DeveloperBot()

@bot.event
async def on_ready():
    log.info(f"🤖 Bot is online as {bot.user} (ID: {bot.user.id})")
    log.info(f"Connected Guilds: {[g.name for g in bot.guilds]}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ ليس لديك الصلاحيات الكافية لتنفيذ هذا الأمر.")
    else:
        log.warning(f"Command error: {error}")

if __name__ == "__main__":
    if not TOKEN:
        log.critical("Missing DISCORD_TOKEN in environment or .env file!")
        raise RuntimeError("DISCORD_TOKEN is missing. Please set it in .env file.")

    bot.run(TOKEN)
