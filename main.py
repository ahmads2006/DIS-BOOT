import asyncio
import os
import signal
import sys
import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID, API_PORT
from core.logging import log, measure_duration
from core.sentry import init_sentry, capture_interaction_error, capture_exception, flush as sentry_flush
from database.connection import (
    verify_connectivity,
    run_pending_migrations,
    start_pool_monitor,
    release as db_pool_release,
)
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

        # ── 1. Database Connectivity Check & Migrations ──
        log.info("Verifying database connectivity...")
        db_connected = await verify_connectivity()
        if db_connected:
            log.info("Database connectivity verified successfully. Running pending migrations...")
            await run_pending_migrations()
        else:
            log.warning("Database connectivity check failed or connection pool is not yet available.")

        # Legacy database initialization
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
                capture_exception(e, tags={"extension": ext})

        # ── 6. ByteDaily cog ──
        # DynamicItems are registered at the start of cog_load() BEFORE DB init.
        try:
            await self.load_extension("features.bytedaily.cog")
            log.info("Loaded extension: features.bytedaily.cog")
        except Exception as e:
            log.error(f"Failed to load ByteDaily extension: {e}")
            capture_exception(e, tags={"extension": "features.bytedaily.cog"})

        # ── 7. Warm up ByteDaily active poll cache ──
        try:
            from features.bytedaily.services import poll_service
            active_poll = await poll_service.get_open_poll()
            if active_poll:
                log.info(f"ByteDaily active poll cache warmed: Active poll #{active_poll['id']} found.")
            else:
                log.info("ByteDaily active poll cache warmed: No currently open poll.")
        except Exception as e:
            log.warning(f"ByteDaily: Failed to warm up active poll cache: {e}")

        # Start pool health monitor background worker
        start_pool_monitor()

        # ── 8. Slash command sync (AFTER all extensions) ──
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
            capture_exception(e, tags={"component": "tree_sync"})

        # ── 9. Legacy persistent views ──
        from legacy.views.exam_views import ExamPanelLaunchView
        self.add_view(ExamPanelLaunchView(self))
        log.info("Registered Persistent ExamPanelLaunchView.")

        # ── 10. ByteDaily persistent views ──
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
        from core.http_client import get_http_session
        while not self.is_closed():
            try:
                session = await get_http_session()
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    log.info(f"Keepalive ping {url} → HTTP {resp.status}")
            except Exception as e:
                log.warning(f"Keepalive ping failed ({url}): {e}")
            await asyncio.sleep(max(60, interval))

    async def close(self):
        log.info("Initiating graceful bot shutdown sequence...")
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
        if self.api_server:
            await self.api_server.stop()

        # Persist / clean up active exam sessions
        try:
            from legacy.core.state import active_exams
            if active_exams:
                log.warning(f"Shutdown: Saving/cleaning up {len(active_exams)} active exam session(s)...")
                for u_id, exam_info in list(active_exams.items()):
                    task = exam_info.get("task")
                    if task and not task.done():
                        task.cancel()
                    try:
                        await db.record_fail(u_id, exam_info.get("role_key", "unknown"))
                    except Exception:
                        pass
                active_exams.clear()
        except Exception as e:
            log.warning(f"Shutdown: Error cleaning up active exams: {e}")

        # Close persistent global HTTP session
        try:
            from core.http_client import close_http_session
            await close_http_session()
        except Exception as e:
            log.warning(f"Error closing HTTP session: {e}")

        # Close database connection pools
        try:
            from features.bytedaily.database.client import bd_db
            await bd_db.close()
        except Exception:
            pass
        await db.close()
        await db_pool_release()

        # Flush pending Sentry events before exit
        sentry_flush(timeout=2.0)

        await super().close()
        log.info("Bot shutdown completed cleanly.")


bot = DeveloperBot()

@bot.event
async def on_ready():
    log.info(f"🤖 Bot is online as {bot.user} (ID: {bot.user.id})")
    log.info(f"Connected Guilds: {[g.name for g in bot.guilds]}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ ليس لديك الصلاحيات الكافية لتنفيذ هذا الأمر. | You do not have sufficient permissions to execute this command.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        log.warning(f"Command error: {error}")
        capture_exception(
            error,
            tags={
                "command": str(ctx.command),
                "author_id": ctx.author.id,
                "guild_id": ctx.guild.id if ctx.guild else "DM",
            },
        )

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    log.error(f"App command error: {error}", exc_info=True)
    capture_interaction_error(interaction, error)
    try:
        msg = "⚠️ حدث خطأ أثناء تنفيذ الأمر. حاول مرة أخرى. | An error occurred while executing the command. Please try again."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

if __name__ == "__main__":
    # Initialize Sentry error observability
    init_sentry()

    if not TOKEN:
        log.critical("Missing DISCORD_TOKEN in environment or .env file!")
        raise RuntimeError("DISCORD_TOKEN is missing. Please set it in .env file.")

    def _setup_signal_handlers():
        """Setup cross-platform signal handling for graceful shutdown."""
        def _handle_signal(sig, frame):
            log.info(f"Received shutdown signal {sig}, terminating gracefully...")
            if bot.loop and bot.loop.is_running():
                asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _handle_signal)
        except Exception as e:
            log.warning(f"Could not bind signal handlers: {e}")

    _setup_signal_handlers()

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
            except (KeyboardInterrupt, SystemExit):
                log.info("Shutdown interrupted by user/system.")
                if not bot.is_closed():
                    await bot.close()
                break

    try:
        asyncio.run(_start_with_rate_limit_retry())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot execution finished.")
