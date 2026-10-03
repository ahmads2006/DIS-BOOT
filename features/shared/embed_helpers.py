"""
Shared Embed Helpers — Reusable embed formatting utilities.

Provides pure helper functions for consistent embed styling across features.
Returns discord.Embed objects — does NOT send messages or call Discord APIs.
Import these from any feature that needs standard embed formatting.
"""

from datetime import datetime, timezone
from typing import Optional
import discord


def make_info_embed(
    title: str,
    description: str,
    color: Optional[discord.Color] = None,
) -> discord.Embed:
    """Create a standard informational embed with timestamp."""
    return discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )


def make_error_embed(title: str, description: str) -> discord.Embed:
    """Create a red-coloured error embed."""
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc),
    )


def make_success_embed(title: str, description: str) -> discord.Embed:
    """Create a green-coloured success embed."""
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    )


def add_guild_branding(
    embed: discord.Embed,
    guild: Optional[discord.Guild] = None,
) -> discord.Embed:
    """
    Add guild icon as thumbnail and guild name as footer if available.
    Mutates and returns the embed for chaining.
    """
    if guild:
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=guild.name)
    return embed
