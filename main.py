import asyncio
import os
import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID
from core.logger import log
from core.database import db
from api.server import AsyncAPIServer

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

        # تهيئة طبقة قاعدة البيانات
        await db.initialize()

        # تحميل الموديولات (Cogs)
        initial_extensions = [
            "cogs.onboarding",
            "cogs.exam",
            "cogs.admin",
            "cogs.stats",
        ]

        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                log.info(f"Loaded extension: {ext}")
            except Exception as e:
                log.error(f"Failed to load extension {ext}: {e}")

        # مزامنة أوامر السلاش
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

        # تشغيل خادم الـ API غير المتزامن
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
