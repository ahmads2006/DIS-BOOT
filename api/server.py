import discord
from aiohttp import web
from config import BOT_API_KEY, API_HOST, API_PORT
from core.logger import log
from core.exam_engine import start_exam_core, send_next_question

class AsyncAPIServer:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.app = web.Application()
        self.runner = None
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/api/health", self.health_check)
        self.app.router.add_post("/api/start-exam", self.start_exam_endpoint)

    async def health_check(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "online",
            "bot_ready": self.bot.is_ready(),
            "latency_ms": round(self.bot.latency * 1000, 2) if self.bot.is_ready() else None
        })

    async def start_exam_endpoint(self, request: web.Request) -> web.Response:
        # التحقق من مفتاح الـ API
        api_key = request.headers.get("X-API-KEY")
        if api_key != BOT_API_KEY:
            return web.json_response({"error": "Unauthorized"}, status=401)

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        user_id = data.get("discord_user_id")
        role = data.get("role")
        guild_id = data.get("guild_id", 0)

        if not user_id or not role:
            return web.json_response({"error": "Missing discord_user_id or role"}, status=400)

        try:
            user = self.bot.get_user(int(user_id)) or await self.bot.fetch_user(int(user_id))
        except Exception as e:
            return web.json_response({"error": f"User not found: {e}"}, status=404)

        status, *extra = await start_exam_core(
            bot=self.bot,
            user=user,
            guild_id=int(guild_id),
            role_key=role,
            lang="ar"
        )

        if status == "ok":
            dm_channel = extra[0]
            await send_next_question(self.bot, user, dm_channel)
            return web.json_response({"status": "exam_started", "user_id": user_id, "role": role})
        elif status == "cooldown":
            return web.json_response({"status": "cooldown", "remaining_hours": extra[0]}, status=429)
        elif status == "already_active":
            return web.json_response({"status": "already_active"}, status=409)
        else:
            return web.json_response({"status": status}, status=400)

    async def start(self):
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, host=API_HOST, port=API_PORT)
            await site.start()
            log.info(f"⚡ Async API Server running at http://{API_HOST}:{API_PORT}")
        except Exception as e:
            log.error(f"Failed to start API Server on port {API_PORT}: {e}")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            log.info("API Server stopped.")
