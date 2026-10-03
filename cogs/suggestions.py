import discord
from discord.ext import commands

import time
from dataclasses import dataclass, field
from typing import Literal

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..main import PG_Bot

SuggestionKind = Literal["sotw", "qotw"]

THREAD_CONFIG_KEYS: dict[SuggestionKind, str] = {
    "sotw": "SOTW_SUGGESTION_THREAD",
    "qotw": "QOTW_SUGGESTION_THREAD",
}

EMBED_TITLES: dict[SuggestionKind, str] = {
    "sotw": "🎵 SOTW suggestion",
    "qotw": "❓ QOTW suggestion",
}

@dataclass
class Suggestion:
    """A single SOTW/QOTW suggestion, shaped so it can be persisted to the database later on"""
    kind: SuggestionKind
    user_id: int
    guild_id: int
    fields: dict[str, str]
    created_at: float = field(default_factory=time.time)


class SotwModal(discord.ui.Modal):

    def __init__(self, cog: "PG_Suggestions"):
        super().__init__(
            discord.ui.InputText(label="Artist", max_length=100),
            discord.ui.InputText(label="Song title", max_length=100),
            discord.ui.InputText(label="Link", required=False, max_length=200),
            discord.ui.InputText(label="Why this song?", style=discord.InputTextStyle.long, required=False, max_length=500),
            title="Suggest a Song Of The Week",
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.submit_suggestion(interaction, "sotw", self.children)


class QotwModal(discord.ui.Modal):

    def __init__(self, cog: "PG_Suggestions"):
        super().__init__(
            discord.ui.InputText(label="Question", style=discord.InputTextStyle.long, max_length=500),
            title="Suggest a Question Of The Week",
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.submit_suggestion(interaction, "qotw", self.children)


class PG_Suggestions(commands.Cog):
    """
    Private SOTW/QOTW suggestions, forwarded to mod-only threads
    """

    suggest = discord.SlashCommandGroup("suggest", "Suggest a Song or Question of the Week")

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot
        self._last_submit: dict[tuple[int, SuggestionKind], float] = {}

    @suggest.command(name="sotw", description="Suggest a Song Of The Week")
    async def suggest_sotw(self, ctx: discord.ApplicationContext):
        if await self._check_can_suggest(ctx, "sotw"):
            await ctx.send_modal(SotwModal(self))

    @suggest.command(name="qotw", description="Suggest a Question Of The Week")
    async def suggest_qotw(self, ctx: discord.ApplicationContext):
        if await self._check_can_suggest(ctx, "qotw"):
            await ctx.send_modal(QotwModal(self))

    #================================================================================
    # Helpers

    def _cooldown_remaining(self, user_id: int, kind: SuggestionKind) -> int:
        cooldown = int(self.bot.db.get_config_value("SUGGESTION_COOLDOWN", "0")) # type: ignore
        last = self._last_submit.get((user_id, kind))
        if last is None:
            return 0
        return max(0, int(last + cooldown - time.time()))

    async def _check_can_suggest(self, ctx: discord.ApplicationContext, kind: SuggestionKind) -> bool:
        if ctx.guild is None:
            await ctx.respond("Suggestions can only be made in the server.", ephemeral=True)
            return False

        if not self.bot.db.get_config_value(THREAD_CONFIG_KEYS[kind]):
            await ctx.respond(f"{kind.upper()} suggestions aren't set up yet.", ephemeral=True)
            return False

        if remaining := self._cooldown_remaining(ctx.author.id, kind):
            minutes = (remaining + 59) // 60
            await ctx.respond(f"You can suggest another {kind.upper()} in {minutes} minute(s).", ephemeral=True)
            return False

        return True

    async def _get_suggestion_thread(self, guild: discord.Guild, kind: SuggestionKind) -> discord.Thread | None:
        thread_id = self.bot.db.get_config_value(THREAD_CONFIG_KEYS[kind])
        if not thread_id:
            return None

        # Archived threads are not in the cache, so fall back to fetching
        thread = guild.get_channel_or_thread(int(thread_id))
        if thread is None:
            try:
                thread = await guild.fetch_channel(int(thread_id))
            except (discord.NotFound, discord.Forbidden):
                return None

        return thread if isinstance(thread, discord.Thread) else None

    async def submit_suggestion(self, interaction: discord.Interaction, kind: SuggestionKind, inputs: list):
        user = interaction.user
        guild = interaction.guild
        if user is None or guild is None:
            await interaction.response.send_message("Something went wrong, please try again.", ephemeral=True)
            return

        suggestion = Suggestion(
            kind=kind,
            user_id=user.id,
            guild_id=guild.id,
            fields={i.label: i.value for i in inputs if i.value},
        )

        thread = await self._get_suggestion_thread(guild, kind)
        if thread is None:
            await interaction.response.send_message("Couldn't deliver your suggestion, please let a moderator know.", ephemeral=True)
            return

        embed = discord.Embed(title=EMBED_TITLES[kind], timestamp=discord.utils.utcnow())
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.add_field(name="Suggested by", value=user.mention, inline=False)
        for label, value in suggestion.fields.items():
            embed.add_field(name=label, value=value, inline=False)

        try:
            if thread.archived and not thread.locked:
                await thread.edit(archived=False)
            await thread.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            print(f"Failed to post {kind} suggestion to thread {thread.id}: {e}")
            await interaction.response.send_message("Couldn't deliver your suggestion, please let a moderator know.", ephemeral=True)
            return

        # TODO: persist suggestion to DB, e.g. await self.bot.db.add_suggestion(suggestion)

        self._last_submit[(user.id, kind)] = suggestion.created_at
        await interaction.response.send_message(f"{user.mention} just suggested a {kind.upper()}!")

def setup(bot: "PG_Bot"):
    bot.add_cog(PG_Suggestions(bot))
    print("Added cog: 'PG_Suggestions'")
