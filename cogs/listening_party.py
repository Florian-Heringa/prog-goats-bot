import discord
from discord.ext import commands

import asyncio

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..main import PG_Bot

class PG_ListeningParty(commands.Cog):

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot

    @discord.slash_command(name='countdown')
    @commands.has_role("Party Animals")
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