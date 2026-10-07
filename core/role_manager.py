"""
Role Manager — Automated Discord role management, creation, and tier synchronization.

Handles:
  1. Auto-creating track specialization and developer tier roles if missing.
  2. Setup all server roles in one click (/setup-roles).
  3. Seamless level progression role synchronization with lower tier cleanup.
  4. Public promotion celebration embeds in general chat.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import discord

from config import ROLE_MAP, TIER_ROLES, TRACK_ROLE_METADATA
from core.logging import log


import re

def normalize_role_name(name: str) -> str:
    """Normalize role string by stripping all emojis, symbols, bars, and spaces, keeping only lowercase alphanumeric."""
    return re.sub(r"[^a-zA-Z0-9\u0600-\u06FF]", "", name).lower()



async def find_or_create_role(
    guild: discord.Guild,
    role_name: str,
    color_hex: int = 0x5865F2,
    reason: str = "DevQuest Engine Automated Role Setup",
) -> Tuple[Optional[discord.Role], bool]:
    """
    Find an existing role or create it if not found.
    Returns (discord.Role, was_created: bool).
    """
    # 1. Exact match
    role = discord.utils.get(guild.roles, name=role_name)
    if role:
        return role, False

    # 2. Normalized match
    norm_target = normalize_role_name(role_name)
    for r in guild.roles:
        if normalize_role_name(r.name) == norm_target:
            return r, False

    # 3. Create role if bot has permissions
    bot_member = guild.me
    if not bot_member or not bot_member.guild_permissions.manage_roles:
        log.warning(f"RoleManager: Bot lacks 'manage_roles' permission in guild '{guild.name}'. Cannot create '{role_name}'.")
        return None, False

    try:
        new_role = await guild.create_role(
            name=role_name,
            color=discord.Color(color_hex),
            reason=reason,
            mentionable=False,
        )
        log.info(f"RoleManager: Created role '{role_name}' with color #{color_hex:06X} in '{guild.name}'.")
        return new_role, True
    except discord.Forbidden:
        log.error(f"RoleManager: Forbidden from creating role '{role_name}' in '{guild.name}'.")
        return None, False
    except Exception as e:
        log.error(f"RoleManager: Error creating role '{role_name}' in '{guild.name}': {e}", exc_info=True)
        return None, False


async def setup_all_server_roles(guild: discord.Guild) -> Dict[str, Any]:
    """
    Set up all specialization and developer tier roles in a guild.
    Returns detailed summary of created, existing, and failed roles.
    """
    created_roles: List[str] = []
    existing_roles: List[str] = []
    failed_roles: List[str] = []

    # 1. Developer Level Tier Roles
    for tier in TIER_ROLES:
        role_name = tier["name"]
        color_hex = tier["color"]
        role_obj, was_created = await find_or_create_role(
            guild=guild,
            role_name=role_name,
            color_hex=color_hex,
            reason="DevQuest /setup-roles initialization (Developer Level Tiers)",
        )
        if was_created:
            created_roles.append(f"⭐ **{role_name}** (`{tier['min_points']}+ pts`)")
        elif role_obj:
            existing_roles.append(f"⭐ {role_obj.mention}")
        else:
            failed_roles.append(f"⭐ {role_name}")

    # 2. Track Specialization Roles
    for track_key, meta in TRACK_ROLE_METADATA.items():
        role_name = meta["name"]
        color_hex = meta["color"]
        role_obj, was_created = await find_or_create_role(
            guild=guild,
            role_name=role_name,
            color_hex=color_hex,
            reason="DevQuest /setup-roles initialization (Track Specializations)",
        )
        if was_created:
            created_roles.append(f"🛠️ **{role_name}**")
        elif role_obj:
            existing_roles.append(f"🛠️ {role_obj.mention}")
        else:
            failed_roles.append(f"🛠️ {role_name}")

    return {
        "created": created_roles,
        "existing": existing_roles,
        "failed": failed_roles,
        "total_managed": len(TIER_ROLES) + len(TRACK_ROLE_METADATA),
    }


def get_tier_for_points(points: int) -> Optional[Dict[str, Any]]:
    """Get highest eligible tier dictionary for a given point score."""
    for tier in TIER_ROLES:
        if points >= tier["min_points"]:
            return tier
    return None


async def sync_developer_tier_role(
    member: discord.Member,
    total_points: int,
    general_channel: Optional[discord.TextChannel] = None,
) -> Optional[Dict[str, Any]]:
    """
    Synchronize member's developer tier role based on total points.
    - Removes outdated lower/higher tier roles.
    - Awards current tier role.
    - Sends celebration announcement to general_channel if upgraded.
    """
    guild = member.guild
    bot_member = guild.me

    if not bot_member or not bot_member.guild_permissions.manage_roles:
        return None

    target_tier = get_tier_for_points(total_points)
    if not target_tier:
        return None

    # Collect all tier role objects in guild
    all_tier_role_names = {t["name"] for t in TIER_ROLES}
    all_tier_roles: Dict[str, discord.Role] = {}
    for r in guild.roles:
        norm = normalize_role_name(r.name)
        for t in TIER_ROLES:
            if normalize_role_name(t["name"]) == norm:
                all_tier_roles[t["name"]] = r

    target_role_obj = all_tier_roles.get(target_tier["name"])
    if not target_role_obj:
        target_role_obj, _ = await find_or_create_role(
            guild=guild,
            role_name=target_tier["name"],
            color_hex=target_tier["color"],
            reason="DevQuest Tier Progression auto-creation",
        )

    if not target_role_obj:
        return None

    # Check hierarchy
    if bot_member.top_role.position <= target_role_obj.position:
        log.warning(
            f"RoleManager: Bot top role '{bot_member.top_role.name}' is lower than tier role '{target_role_obj.name}' in '{guild.name}'."
        )
        return None

    # Identify member's current tier roles
    current_member_tier_roles = [
        r for r in member.roles if normalize_role_name(r.name) in [normalize_role_name(name) for name in all_tier_role_names]
    ]

    has_target_role = target_role_obj in member.roles
    roles_to_remove = [r for r in current_member_tier_roles if r != target_role_obj]

    # If member already has target role and no old roles to clean up, nothing to do
    if has_target_role and not roles_to_remove:
        return None

    try:
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="DevQuest Tier Progression cleanup")
            log.info(f"RoleManager: Removed {[r.name for r in roles_to_remove]} from {member.name}")

        if not has_target_role:
            await member.add_roles(target_role_obj, reason=f"DevQuest Tier Progression: Reached {total_points} pts")
            log.info(f"RoleManager: Awarded tier role '{target_role_obj.name}' to {member.name} ({member.id})")

            # Promotion announcement
            if general_channel:
                try:
                    embed = discord.Embed(
                        title="🎉 ترقية برمجية جديدة! • New Developer Tier Reached!",
                        description=(
                            f"🌟 **تهانينا للمطور المتميز {member.mention}!**\n\n"
                            f"📈 ارتقى مستواه في **ByteDaily** إلى رتبة جديدة:\n"
                            f"🏷️ {target_role_obj.mention} — **{target_tier['title_ar']}** (`{target_tier['title_en']}`)\n"
                            f"⭐ إجمالي النقاط الحالية: **{total_points}** pts\n\n"
                            f"> 🚀 *استمر في حل التحديات اليومية للارتقاء نحو أعلى المراتب البرمجية!*"
                        ),
                        color=discord.Color(target_tier["color"]),
                        timestamp=datetime.now(timezone.utc),
                    )
                    avatar_url = member.display_avatar.url if hasattr(member, "display_avatar") else None
                    if avatar_url:
                        embed.set_thumbnail(url=avatar_url)
                    embed.set_footer(text="DevQuest Engine • Developer Gamification & Tier Sync")

                    await general_channel.send(
                        content=f"📣 باركوا للمطور {member.mention} على رتبته الجديدة! 🚀",
                        embed=embed,
                    )
                except Exception as e:
                    log.warning(f"RoleManager: Could not send promotion announcement: {e}")

            return {
                "user_id": member.id,
                "tier": target_tier,
                "role_name": target_role_obj.name,
                "upgraded": not has_target_role,
            }

    except Exception as e:
        log.error(f"RoleManager: Error updating tier roles for {member.name}: {e}", exc_info=True)
        return None
