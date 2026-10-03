"""
Shared Embed Helpers — Reusable embed formatting utilities.

Provides pure helper functions for consistent embed styling across features.
Returns discord.Embed objects — does NOT send messages or call Discord APIs.
Import these from any feature that needs standard embed formatting.
"""

# TODO: Import discord
# TODO: Import datetime

# TODO: def make_info_embed(title: str, description: str,
#                            color: discord.Color | None = None) -> discord.Embed:
#   """Create a standard informational embed with timestamp."""
#   TODO: embed = discord.Embed(
#           title=title,
#           description=description,
#           color=color or discord.Color.blurple(),
#           timestamp=datetime.datetime.utcnow(),
#       )
#   TODO: return embed

# TODO: def make_error_embed(title: str, description: str) -> discord.Embed:
#   """Create a red-coloured error embed."""
#   TODO: return discord.Embed(title=title, description=description,
#                               color=discord.Color.red())

# TODO: def make_success_embed(title: str, description: str) -> discord.Embed:
#   """Create a green-coloured success embed."""
#   TODO: return discord.Embed(title=title, description=description,
#                               color=discord.Color.green())

# TODO: def add_guild_branding(embed: discord.Embed,
#                               guild: discord.Guild) -> discord.Embed:
#   """
#   Add guild icon as thumbnail and guild name as footer.
#   Mutates and returns the embed for chaining.
#   """
#   TODO: if guild.icon:
#           embed.set_thumbnail(url=guild.icon.url)
#   TODO: embed.set_footer(text=guild.name)
#   TODO: return embed
