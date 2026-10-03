import discord
from discord.ext import commands, tasks

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

from database import Reminder

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..main import PG_Bot

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
TIME_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
MAX_REMINDERS = 25          # Maximum amount of options in a select menu
MISSED_GRACE_SECONDS = 3600 # Reminders overdue by more than this (e.g. bot was offline) are skipped
TIMEZONES = sorted(available_timezones())
REMINDER_CHANNEL_TYPES = [
    discord.ChannelType.text,
    discord.ChannelType.news,
    discord.ChannelType.public_thread,
    discord.ChannelType.private_thread,
]
# Only user mentions ping, so nobody can use the bot to ping @everyone or roles they couldn't ping themselves
REMINDER_MENTIONS = discord.AllowedMentions(everyone=False, roles=False, users=True)

#================================================================================
# Helpers

def parse_time(value: str) -> str | None:
    """Parses a 24-hour 'HH:MM' time, returns it normalized or None when invalid"""
    match = TIME_PATTERN.match(value.strip())
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"

def parse_day(value: str) -> int | None:
    """Accepts a full day name or its first three letters, returns 0 (monday) to 6 (sunday)"""
    value = value.strip().lower()
    for i, day in enumerate(DAYS):
        if len(value) >= 3 and day.startswith(value):
            return i
    return None

def compute_next_run(weekday: int, time_of_day: str, timezone: str, after: float) -> float:
    """
    Next moment after 'after' that falls on 'weekday' at 'time_of_day' in 'timezone'.
    Calculated in local wall-clock time, so the reminder stays at the same local time across DST changes.
    """
    hour, minute = map(int, time_of_day.split(":"))
    now_local = datetime.fromtimestamp(after, ZoneInfo(timezone))
    candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    candidate += timedelta(days=(weekday - now_local.weekday()) % 7)
    if candidate.timestamp() <= after:
        candidate += timedelta(days=7)
    return candidate.timestamp()

def check_can_post(channel: discord.TextChannel | discord.Thread, member: discord.Member) -> str | None:
    """Returns why the member or the bot can't post in the channel, or None when both can"""
    for who, name in ((member, "You"), (channel.guild.me, "The bot")):
        perms = channel.permissions_for(who)
        can_send = perms.send_messages_in_threads if isinstance(channel, discord.Thread) else perms.send_messages
        if not (perms.view_channel and can_send):
            return f"{name} can't post in {channel.mention}."
    return None

def describe_destination(channel_id: int | None) -> str:
    return f"<#{channel_id}>" if channel_id else "your DMs"

def describe_reminder(reminder: Reminder) -> str:
    return (
        f"**{DAYS[reminder.weekday].capitalize()} {reminder.time_of_day}** in {describe_destination(reminder.channel_id)}\n"
        f"{reminder.text}\n"
        f"-# Next reminder: <t:{int(reminder.next_run)}:F>"
    )

async def timezone_autocomplete(ctx: discord.AutocompleteContext) -> list[str]:
    query = (ctx.value or "").lower()
    return [tz for tz in TIMEZONES if query in tz.lower()][:25]

#================================================================================
# Edit UI

class ReminderModal(discord.ui.DesignerModal):
    """DesignerModal instead of Modal, because only those can hold a select menu (the channel picker)"""

    def __init__(self, view: "ReminderEditView", reminder: Reminder):
        self.time_input = discord.ui.InputText(value=reminder.time_of_day, max_length=5)
        self.day_input = discord.ui.InputText(value=DAYS[reminder.weekday], max_length=9)
        self.text_input = discord.ui.InputText(value=reminder.text, style=discord.InputTextStyle.long, max_length=1000)
        self.channel_select = discord.ui.Select(
            select_type=discord.ComponentType.channel_select,
            channel_types=REMINDER_CHANNEL_TYPES,
            required=False,
            min_values=0,
            placeholder="Your DMs",
            default_values=[
                discord.SelectDefaultValue(id=reminder.channel_id, type=discord.SelectDefaultValueType.channel)
            ] if reminder.channel_id else None,
        )
        super().__init__(
            discord.ui.Label("Time (24-hour HH:MM)", self.time_input),
            discord.ui.Label("Day", self.day_input),
            discord.ui.Label("Text", self.text_input),
            discord.ui.Label("Channel", self.channel_select, description="Leave empty to get the reminder in your DMs"),
            title="Edit reminder",
        )
        self.edit_view = view
        self.reminder = reminder

    async def callback(self, interaction: discord.Interaction):
        time_of_day = parse_time(self.time_input.value or "")
        weekday = parse_day(self.day_input.value or "")
        text = (self.text_input.value or "").strip()
        if time_of_day is None or weekday is None or not text:
            await interaction.response.send_message(
                "Invalid input, use a 24-hour time like `20:00`, a day like `tuesday`, and a non-empty text.",
                ephemeral=True
            )
            return

        channel_id = None
        selected = self.channel_select.values or []
        if selected:
            channel = await self.edit_view.cog.resolve_channel(selected[0].id)
            if channel is None or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message("Can't use that channel for reminders.", ephemeral=True)
                return
            if problem := check_can_post(channel, interaction.user):
                await interaction.response.send_message(problem, ephemeral=True)
                return
            channel_id = channel.id

        await self.edit_view.cog.save_reminder(self.edit_view.user_id, self.reminder.id, weekday, time_of_day, text, channel_id)
        updated = await self.edit_view.cog.bot.db.get_reminder(self.edit_view.user_id, self.reminder.id)

        # The modal was opened from the edit message, so the response can update that message in place
        await self.edit_view.refresh()
        await interaction.response.edit_message(
            content="Reminder updated:\n" + describe_reminder(updated) if updated else "Reminder updated.",
            view=self.edit_view.or_none(),
        )


class ReminderEditView(discord.ui.View):
    """Ephemeral view: pick a reminder from the dropdown, then edit or delete it"""

    def __init__(self, cog: "PG_Reminders", user_id: int, reminders: list[Reminder]):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.reminders = reminders
        self.selected: Reminder | None = None

        self.select = discord.ui.Select(placeholder="Choose a reminder")
        self.select.callback = self.on_select

        self.edit_button = discord.ui.Button(label="Edit", style=discord.ButtonStyle.primary, disabled=True)
        self.edit_button.callback = self.on_edit

        self.delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, disabled=True)
        self.delete_button.callback = self.on_delete

        self.add_item(self.select)
        self.add_item(self.edit_button)
        self.add_item(self.delete_button)
        self._build_options()

    def _build_options(self):
        self.select.options = [
            discord.SelectOption(
                label=f"{DAYS[r.weekday].capitalize()} {r.time_of_day} — {r.text}"[:100],
                value=str(r.id),
            )
            for r in self.reminders
        ]
        self.selected = None
        self.edit_button.disabled = True
        self.delete_button.disabled = True

    async def refresh(self):
        self.reminders = await self.cog.bot.db.get_user_reminders(self.user_id)
        self._build_options()

    def or_none(self) -> "ReminderEditView | None":
        return self if self.reminders else None

    async def on_select(self, interaction: discord.Interaction):
        values = self.select.values or []
        self.selected = next((r for r in self.reminders if values and str(r.id) == values[0]), None)
        if self.selected is None:
            await interaction.response.send_message("That reminder no longer exists.", ephemeral=True)
            return

        self.edit_button.disabled = False
        self.delete_button.disabled = False
        await interaction.response.edit_message(content=describe_reminder(self.selected), view=self)

    async def on_edit(self, interaction: discord.Interaction):
        if self.selected is None:
            return
        await interaction.response.send_modal(ReminderModal(self, self.selected))

    async def on_delete(self, interaction: discord.Interaction):
        if self.selected is None:
            return
        await self.cog.bot.db.delete_reminder(self.user_id, self.selected.id)
        deleted = self.selected
        await self.refresh()
        await interaction.response.edit_message(
            content=f"Deleted reminder: {DAYS[deleted.weekday].capitalize()} {deleted.time_of_day}"
                    + ("" if self.reminders else "\nYou have no reminders left."),
            view=self.or_none(),
        )

#================================================================================
# Cog

class PG_Reminders(commands.Cog):
    """
    Weekly reminders by DM or in a channel, e.g. for the people posting the QOTW and SOTW
    """

    # Hidden by default, enable per user or role in Server Settings -> Integrations
    reminder = discord.SlashCommandGroup(
        "reminder",
        "Weekly reminders",
        default_member_permissions=discord.Permissions(administrator=True),
    )

    def __init__(self, bot: "PG_Bot"):
        self.bot: "PG_Bot" = bot
        self.send_due_reminders.start()

    def cog_unload(self):
        self.send_due_reminders.cancel()

    async def save_reminder(self, user_id: int, reminder_id: int, weekday: int, time_of_day: str, text: str, channel_id: int | None):
        timezone = await self.bot.db.get_user_timezone(user_id) or "UTC"
        next_run = compute_next_run(weekday, time_of_day, timezone, discord.utils.utcnow().timestamp())
        await self.bot.db.update_reminder(user_id, reminder_id, weekday, time_of_day, text, next_run, channel_id)

    async def resolve_channel(self, channel_id: int) -> discord.TextChannel | discord.Thread | None:
        """Cached channel when possible, otherwise fetched (archived threads aren't cached)"""
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                return None
        return channel if isinstance(channel, (discord.TextChannel, discord.Thread)) else None

    async def get_member(self, guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden):
                return None
        return member

    @reminder.command(name="timezone", description="Set your timezone, used for all your reminders")
    @discord.option("timezone", type=str, description="Start typing to search for your timezone, for example: Europe/Amsterdam", autocomplete=timezone_autocomplete)
    async def set_timezone(self, ctx: discord.ApplicationContext, timezone: str):
        if timezone not in TIMEZONES:
            await ctx.respond("Unknown timezone, pick one from the list, for example `Europe/Amsterdam`.", ephemeral=True)
            return

        await self.bot.db.set_user_timezone(ctx.author.id, timezone)

        # Existing reminders keep their local time, so their next moment changes
        now = discord.utils.utcnow().timestamp()
        for r in await self.bot.db.get_user_reminders(ctx.author.id):
            await self.bot.db.set_reminder_next_run(r.id, compute_next_run(r.weekday, r.time_of_day, timezone, now))

        await ctx.respond(f"Your timezone is now `{timezone}`.", ephemeral=True)

    @reminder.command(name="set", description="Get a weekly reminder by DM or in a channel")
    @discord.option("time", type=str, description="24-hour time in your timezone, for example 20:00")
    @discord.option("day", type=str, choices=[discord.OptionChoice(name=d.capitalize(), value=d) for d in DAYS])
    @discord.option("text", type=str, description="What the reminder should say", max_length=1000)
    @discord.option(
        "channel",
        type=discord.SlashCommandOptionType.channel,
        channel_types=REMINDER_CHANNEL_TYPES,
        description="Channel to post the reminder in, leave empty to get it in your DMs",
        required=False,
        default=None,
    )
    async def set_reminder(self, ctx: discord.ApplicationContext, time: str, day: str, text: str, channel: discord.abc.GuildChannel | None):
        timezone = await self.bot.db.get_user_timezone(ctx.author.id)
        if timezone is None:
            await ctx.respond("Set your timezone first with `/reminder timezone`.", ephemeral=True)
            return

        time_of_day = parse_time(time)
        if time_of_day is None:
            await ctx.respond("Invalid time, use a 24-hour time like `20:00` or `9:30`.", ephemeral=True)
            return

        if len(await self.bot.db.get_user_reminders(ctx.author.id)) >= MAX_REMINDERS:
            await ctx.respond(f"You can have at most {MAX_REMINDERS} reminders, remove one with `/reminder edit` first.", ephemeral=True)
            return

        channel_id = None
        if channel is not None:
            # Re-resolve, so the permission check uses the full channel (with overwrites) instead of the option data
            target = await self.resolve_channel(channel.id)
            if target is None or not isinstance(ctx.author, discord.Member):
                await ctx.respond("Can't use that channel for reminders.", ephemeral=True)
                return
            if problem := check_can_post(target, ctx.author):
                await ctx.respond(problem, ephemeral=True)
                return
            channel_id = target.id

        weekday = DAYS.index(day)
        next_run = compute_next_run(weekday, time_of_day, timezone, discord.utils.utcnow().timestamp())
        await self.bot.db.add_reminder(ctx.author.id, weekday, time_of_day, text, next_run, channel_id)

        await ctx.respond(
            f"Reminder set for every **{day.capitalize()} at {time_of_day}** ({timezone}) in {describe_destination(channel_id)}.\n"
            f"First reminder: <t:{int(next_run)}:F>"
            + ("" if channel_id else "\n-# Make sure you allow DMs from server members, otherwise the bot can't reach you."),
            ephemeral=True
        )

    @reminder.command(name="edit", description="View, edit or delete your reminders")
    async def edit_reminders(self, ctx: discord.ApplicationContext):
        reminders = await self.bot.db.get_user_reminders(ctx.author.id)
        if not reminders:
            await ctx.respond("You have no reminders, add one with `/reminder set`.", ephemeral=True)
            return

        await ctx.respond("Choose a reminder to edit or delete.", view=ReminderEditView(self, ctx.author.id, reminders), ephemeral=True)

    #================================================================================
    # Scheduling

    @tasks.loop(seconds=30)
    async def send_due_reminders(self):
        now = discord.utils.utcnow().timestamp()
        for reminder in await self.bot.db.get_due_reminders(now):
            # Never let one failing reminder stop the loop
            try:
                if now - reminder.next_run <= MISSED_GRACE_SECONDS:
                    await self.deliver(reminder)
                else:
                    print(f"Skipped reminder {reminder.id}, it was missed by more than {MISSED_GRACE_SECONDS} seconds")
            except discord.Forbidden:
                print(f"Could not DM user {reminder.user_id} for reminder {reminder.id}, DMs are probably closed")
            except Exception as e:
                print(f"Failed to send reminder {reminder.id}: {e}")

            # Always reschedule, so a failure doesn't cause a retry every tick
            timezone = await self.bot.db.get_user_timezone(reminder.user_id) or "UTC"
            await self.bot.db.set_reminder_next_run(
                reminder.id, compute_next_run(reminder.weekday, reminder.time_of_day, timezone, now)
            )

    async def deliver(self, reminder: Reminder):
        """Sends the reminder to its channel, or by DM. Falls back to a DM when the channel can't be used anymore."""
        user = self.bot.get_user(reminder.user_id) or await self.bot.fetch_user(reminder.user_id)
        if reminder.channel_id is None:
            await user.send(reminder.text)
            return

        problem = "the channel no longer exists or the bot can't see it"
        channel = await self.resolve_channel(reminder.channel_id)
        if channel is not None:
            # Re-check at send time, permissions may have changed since the reminder was set
            member = await self.get_member(channel.guild, reminder.user_id)
            problem = "you are no longer in that server" if member is None else check_can_post(channel, member)
            if problem is None:
                try:
                    await channel.send(f"{user.mention} {reminder.text}", allowed_mentions=REMINDER_MENTIONS)
                    return
                except discord.HTTPException as e:
                    problem = f"sending failed ({e.status})"

        print(f"Reminder {reminder.id} could not be posted in channel {reminder.channel_id}: {problem}, sending as DM")
        await user.send(f"Couldn't post your reminder in <#{reminder.channel_id}> ({problem}), here it is:\n{reminder.text}")

    @send_due_reminders.before_loop
    async def before_send_due_reminders(self):
        await self.bot.wait_until_ready()

def setup(bot: "PG_Bot"):
    bot.add_cog(PG_Reminders(bot))
    print("Added cog: 'PG_Reminders'")
