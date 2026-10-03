import discord
from discord.ext import commands

from checks import admin_predicate, get_admin_role_ids

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..main import PG_Bot

class PG_Config(commands.Cog):
    """
    Cog for configuration commands for the ProgGOATs bot
    """

    # Hidden from members without 'Manage Server' unless allowed in Server Settings -> Integrations
    config = discord.SlashCommandGroup(
        "config",
        "Configuration settings",
        default_member_permissions=discord.Permissions(manage_guild=True),
        checks=[admin_predicate],
    )

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot

    @config.command(name="set-welcome-channel")
    async def set_welcome_channel(self, ctx: discord.ApplicationContext):
        if ctx.channel:
            await self.bot.db.set_config_value("WELCOME_CHANNEL", str(ctx.channel.id))
        
        if ctx.guild:
            current_welcome_channel_id = self.bot.db.get_config_value("WELCOME_CHANNEL")
            if current_welcome_channel_id:
                current_welcome_channel = ctx.guild.get_channel(int(current_welcome_channel_id))
        
                await ctx.respond(f"Updated welcome channel, the welcome channel is now {current_welcome_channel}", ephemeral=True)
                return

        await ctx.respond(f"Failed to update welcome channel.", ephemeral=True)

    @config.command(name="set-new-member-role")
    @discord.option("new_member_role", type=discord.SlashCommandOptionType.string)
    async def set_new_member_role_id(self, ctx: discord.ApplicationContext, new_member_role: str):

        if ctx.guild is None:
            await ctx.respond("Guild info cannot be retrieved")
            return

        role = discord.utils.get(ctx.guild.roles, name=new_member_role) 
        if not role:
            await ctx.respond("Can't retrieve role, make sure it is spelled exactly")
            return

        await self.bot.db.set_config_value("NEW_MEMBER_ROLE_ID", str(role.id))

        if role := ctx.guild.get_role(int(self.bot.db.get_config_value("NEW_MEMBER_ROLE_ID"))): # type: ignore
            await ctx.respond(f"Set new member role to {role}", ephemeral=True)
        else:
            await ctx.respond("Failed to set new member role", ephemeral=True)

    @config.command(name="set-new-member-role-timeout")
    @discord.option("timeout", type=int)
    async def set_new_member_role_timeout(self, ctx: discord.ApplicationContext, timeout: int):
        await self.bot.db.set_config_value("NEW_MEMBER_ROLE_DURATION", str(timeout))
        await ctx.respond(f"Timeout for new member role set to {self.bot.db.get_config_value("NEW_MEMBER_ROLE_DURATION")} seconds.", ephemeral=True)

    @config.command(name="set-suggestion-thread")
    @discord.option("kind", type=str, choices=["sotw", "qotw"])
    async def set_suggestion_thread(self, ctx: discord.ApplicationContext, kind: str):
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.respond("Run this command inside the thread suggestions should be posted to.", ephemeral=True)
            return

        await self.bot.db.set_config_value(f"{kind.upper()}_SUGGESTION_THREAD", str(ctx.channel.id))
        await ctx.respond(f"{kind.upper()} suggestions will now be posted in {ctx.channel.mention}", ephemeral=True)

    @config.command(name="set-suggestion-cooldown")
    @discord.option("cooldown", type=int)
    async def set_suggestion_cooldown(self, ctx: discord.ApplicationContext, cooldown: int):
        await self.bot.db.set_config_value("SUGGESTION_COOLDOWN", str(cooldown))
        await ctx.respond(f"Suggestion cooldown set to {self.bot.db.get_config_value("SUGGESTION_COOLDOWN")} seconds.", ephemeral=True)

    async def _set_admin_role_ids(self, role_ids: set[int]):
        await self.bot.db.set_config_value("ADMIN_ROLE_IDS", ",".join(str(role_id) for role_id in sorted(role_ids)))

    @config.command(name="add-admin-role")
    @discord.option("role", type=discord.Role)
    async def add_admin_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        role_ids = get_admin_role_ids(self.bot)
        if role.id in role_ids:
            await ctx.respond(f"{role.mention} is already an admin role.", ephemeral=True)
            return

        await self._set_admin_role_ids(role_ids | {role.id})
        await ctx.respond(f"Added {role.mention} as an admin role.", ephemeral=True)

    @config.command(name="remove-admin-role")
    @discord.option("role", type=discord.Role)
    async def remove_admin_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        role_ids = get_admin_role_ids(self.bot)
        if role.id not in role_ids:
            await ctx.respond(f"{role.mention} is not an admin role.", ephemeral=True)
            return

        await self._set_admin_role_ids(role_ids - {role.id})
        await ctx.respond(f"Removed {role.mention} as an admin role.", ephemeral=True)

    @config.command(name="list-admin-roles")
    async def list_admin_roles(self, ctx: discord.ApplicationContext):
        role_ids = get_admin_role_ids(self.bot)
        if not role_ids:
            await ctx.respond("No admin roles configured, only the bot owner can use admin commands.", ephemeral=True)
            return

        await ctx.respond("Admin roles: " + ", ".join(f"<@&{role_id}>" for role_id in sorted(role_ids)), ephemeral=True)

def setup(bot):
    bot.add_cog(PG_Config(bot))
    print("Added cog: 'PG_Config'")