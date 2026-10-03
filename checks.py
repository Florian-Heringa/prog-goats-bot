import discord
from discord.ext import commands

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import PG_Bot

def get_admin_role_ids(bot: "PG_Bot") -> set[int]:
    """Parses the comma separated 'ADMIN_ROLE_IDS' config value"""
    value = bot.db.get_config_value("ADMIN_ROLE_IDS") or ""
    return {int(role_id) for role_id in value.split(",") if role_id.strip()}

async def admin_predicate(ctx: discord.ApplicationContext) -> bool:
    """The bot owner always passes, so admin roles can be configured before any exist"""
    if await ctx.bot.is_owner(ctx.author):
        return True

    if not isinstance(ctx.author, discord.Member):
        return False

    admin_role_ids = get_admin_role_ids(ctx.bot)
    return any(role.id in admin_role_ids for role in ctx.author.roles)

def is_admin():
    return commands.check(admin_predicate)
