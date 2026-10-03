import discord
from discord.ext import commands

import asyncio

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..main import PG_Bot

class PG_Admin(commands.Cog):

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot

class PG_Testing(commands.Cog):

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot

    # Hidden from non-administrators, narrow down to the owner in Server Settings -> Integrations
    testing = discord.SlashCommandGroup(
        "testing",
        "Commands for testing proper behavior of the bot.",
        default_member_permissions=discord.Permissions(administrator=True),
    )

    @testing.command(name = "debug-join")
    @commands.is_owner()
    async def debug_join(self, ctx: discord.ApplicationContext):
        self.bot.dispatch("member_join", ctx.author)
        await ctx.respond("Dispatched fake join event", ephemeral=True)


def setup(bot: "PG_Bot"):
    bot.add_cog(PG_Admin(bot))
    bot.add_cog(PG_Testing(bot))
    print("Added cog Admin and Testing Cogs")