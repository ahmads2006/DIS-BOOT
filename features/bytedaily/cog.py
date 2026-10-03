"""
ByteDaily Cog — Discord extension entry point.

This Cog is loaded by main.py via bot.load_extension('features.bytedaily.cog').
It is responsible for:
  - Registering the /leaderboard slash command
  - Starting the ByteDaily scheduler loop on cog_load
  - Stopping the scheduler loop on cog_unload
  - Initializing the ByteDaily database pool on cog_load
  - Closing the ByteDaily database pool on cog_unload

The cog does NOT contain business logic — it delegates to services/.
"""

# TODO: Import discord, commands, app_commands
# TODO: Import ByteDailyScheduler from .scheduler
# TODO: Import bd_db from .database.client
# TODO: Import stats_service from .services.stats_service for leaderboard data
# TODO: Import log from bridge.legacy_adapter

# TODO: Define class ByteDailyCog(commands.Cog, name="ByteDaily"):
#   TODO: __init__(self, bot: commands.Bot) — store bot ref, create scheduler instance
#   TODO: async cog_load(self):
#           - await bd_db.initialize()
#           - await self.scheduler.start()
#   TODO: async cog_unload(self):
#           - await self.scheduler.stop()
#           - await bd_db.close()
#   TODO: @app_commands.command(name="leaderboard", ...)
#         async def leaderboard(self, interaction):
#           - await interaction.response.defer()
#           - data = await stats_service.get_leaderboard(limit=10)
#           - build embed with ranked rows (rank, user mention, points, streak)
#           - await interaction.followup.send(embed=embed)

# TODO: async def setup(bot: commands.Bot):
#         await bot.add_cog(ByteDailyCog(bot))
