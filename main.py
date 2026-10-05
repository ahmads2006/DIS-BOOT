import asyncio
import os
import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID, API_PORT
from legacy.core.logger import log
from legacy.core.database import db
from legacy.api.server import AsyncAPIServer

intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.messages = True

class DeveloperBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.api_server = None
        self._keepalive_task = None

    async def setup_hook(self):
        log.info("Starting bot initialization...")

        # ── 0. API server FIRST so Render health checks can keep the dyno awake
        #    while DB/cogs still load (free tier spins down without inbound HTTP).
        self.api_server = AsyncAPIServer(self)
        await self.api_server.start()
        self._keepalive_task = asyncio.create_task(
            self._render_keepalive_loop(),
            name="render-keepalive",
        )

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
        # DynamicItems are registered at the start of cog_load() BEFORE DB init.
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
        log.info("ByteDaily persistent views: DynamicItems registered in ByteDailyCog.cog_load().")

    async def _render_keepalive_loop(self) -> None:
        """
        Ping our own public health URL every few minutes.

        Render free web services sleep after ~15m without *inbound* HTTP.
        Discord's gateway is outbound-only, so without this (or an external
        uptime monitor) the process dies and all clicks/commands time out.
        """
        await self.wait_until_ready()
        base = (
            os.getenv("KEEPALIVE_URL")
            or os.getenv("RENDER_EXTERNAL_URL")
            or ""
        ).rstrip("/")
        if not base:
            # Fall back to localhost — keeps the task harmless in local/dev.
            base = f"http://127.0.0.1:{API_PORT}"
            log.warning(
                "KEEPALIVE_URL / RENDER_EXTERNAL_URL not set — "
                "pinging localhost only. On Render free tier, set KEEPALIVE_URL "
                "to your public service URL (or use UptimeRobot on /api/health) "
                "or the bot will sleep and Discord interactions will time out."
            )

        url = f"{base}/api/health"
        interval = int(os.getenv("KEEPALIVE_INTERVAL_SECONDS", "240"))

        try:
            import aiohttp
        except ImportError:
            log.warning("aiohttp missing — render keepalive disabled.")
            return

        await asyncio.sleep(10)
        while not self.is_closed():
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as resp:
                        log.info(f"Keepalive ping {url} → HTTP {resp.status}")
            except Exception as e:
                log.warning(f"Keepalive ping failed ({url}): {e}")
            await asyncio.sleep(max(60, interval))

    async def close(self):
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
        if self.api_server:
            await self.api_server.stop()
        try:
            from features.bytedaily.database.client import bd_db
            await bd_db.close()
        except Exception:
            pass
        await db.close()
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

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    log.error(f"App command error: {error}", exc_info=True)
    try:
        msg = "⚠️ حدث خطأ أثناء تنفيذ الأمر. حاول مرة أخرى."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

if __name__ == "__main__":
    if not TOKEN:
        log.critical("Missing DISCORD_TOKEN in environment or .env file!")
        raise RuntimeError("DISCORD_TOKEN is missing. Please set it in .env file.")

    async def _start_with_rate_limit_retry() -> None:
        """
        Start the bot with backoff on Discord global 429s.

        Render free-tier cold starts / rapid auto-deploys can hit Discord's
        global rate limit during login. Retrying avoids a hard deploy crash.
        """
        max_attempts = 8
        base_delay = 15  # seconds

        for attempt in range(1, max_attempts + 1):
            try:
                await bot.start(TOKEN)
                return
            except discord.HTTPException as e:
                if e.status != 429 or attempt >= max_attempts:
                    raise

                retry_after = getattr(e, "retry_after", None)
                if retry_after is None:
                    try:
                        raw = e.response.headers.get("Retry-After") if e.response else None
                        retry_after = float(raw) if raw else None
                    except Exception:
                        retry_after = None

                delay = max(float(retry_after or 0), float(base_delay * attempt))
                log.warning(
                    f"Discord rate-limited login (429). "
                    f"Attempt {attempt}/{max_attempts} — sleeping {delay:.0f}s before retry..."
                )
                try:
                    if not bot.is_closed():
                        await bot.close()
                except Exception:
                    pass
                await asyncio.sleep(delay)

    asyncio.run(_start_with_rate_limit_retry())
