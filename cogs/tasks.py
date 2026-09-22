import discord
from discord.ext import commands, tasks

import asyncio

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..main import PG_Bot

class PG_Tasks(commands.Cog):
    """
    A cog for holding timed tasks, recurring tasks or loops.
    """

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot
        self.check_expired_roles.start()

    def cog_unload(self):
        self.check_expired_roles.cancel()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # TODO : proper error handling
        role_id = self.bot.db.get_config_value("NEW_MEMBER_ROLE_ID")
        if role_id is None:
            return

        role = member.guild.get_role(int(role_id))
        if role is None:
            return

        await member.add_roles(role)
        await self.bot.db.add_temp_role(
            member.id, 
            role.id, 
            member.guild.id,
            # Should be populated by default with a meaningful value
            int(self.bot.db.get_config_value("NEW_MEMBER_ROLE_DURATION")) # type: ignore
        )

    @tasks.loop(minutes=10)
    async def check_expired_roles(self):
        expired = await self.bot.db.get_expired_temp_roles()
        for user_id, role_id, guild_id in expired: # type: ignore
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                await self.bot.db.remove_temp_role(user_id, role_id)
                continue

            member = guild.get_member(user_id)
            role = guild.get_role(role_id)
            if member and role and role in member.roles:
                await member.remove_roles(role)

            await self.bot.db.remove_temp_role(user_id, role_id)

    @check_expired_roles.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(PG_Tasks(bot))
    print("Added cog: 'PG_Tasks'")