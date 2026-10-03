import discord
from discord.ext import commands

import traceback

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..main import PG_Bot

class PG_Base(commands.Cog):
    """
    Basic features of the ProgGOATs discord bot
    """

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.bot.user} is ready and online")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild: discord.Guild = member.guild
        channel = guild.get_channel(int(self.bot.db.get_config_value("WELCOME_CHANNEL")))

        if isinstance(channel, discord.TextChannel):
            await channel.send(f"Welcome {member.mention}!")
        else:
            # TODO: Add error logging
            print(f"Welcome channel not found for {guild.name}")

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        if isinstance(error, commands.CheckFailure):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        # Registering this listener disables py-cord's default handler, so print the traceback ourselves
        traceback.print_exception(type(error), error, error.__traceback__)

    # TEST COMMAND
    @discord.slash_command(name="hello", description="Say hello to the bot")
    @discord.default_permissions(administrator=True)
    @commands.is_owner()
    async def hello(self, ctx: discord.ApplicationContext):
        await ctx.respond("Hey, a variation!")

def setup(bot):
    bot.add_cog(PG_Base(bot))
    print("Added cog: 'PG_Base'")