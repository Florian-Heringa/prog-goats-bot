import discord
from discord.ext import commands

import asyncio

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..main import PG_Bot

LISTENING_PARTY_ROLE = "Party Animals"

class PG_ListeningParty(commands.Cog):
    """
    Listening party commands, all top-level and gated behind the listening party role
    """

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot

    async def cog_check(self, ctx: discord.ApplicationContext) -> bool:
        # Applies to every command in this cog; raises MissingRole, handled in PG_Base
        return await commands.has_role(LISTENING_PARTY_ROLE).predicate(ctx)

    @discord.slash_command(name='countdown')
    async def countdown(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        for i in range(5):
            await ctx.send(f"{5-i}")
            await asyncio.sleep(1)
        await ctx.send("GO!")
        await ctx.respond("Enjoy the LP!")

def setup(bot: "PG_Bot"):
    bot.add_cog(PG_ListeningParty(bot))
    print("Added cog: 'PG_ListeningParty'")