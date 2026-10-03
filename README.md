## Prog GOATS Server Discord Bot

Implementation of the Prog GOATS serber Discord bot, handles many features for the server, including:

- Listening Party utilities
- Welcome messages
- Moderator tasks

### Bot Structure

The bot is segmented into several cogs, responsible for different tasks.

- admin.py => General Administrator tasks, also includes debug and testing commands
- base.py => Basic features like welcome messages.
- config.py => Configuration settings commands
- listening_party.py => All commands related to LP tasks. Things like countdowns, planning and sharing resources where to listen
- tasks.py => All recurring tasks that should be run in the background.
- suggestions.py => Private QOTW/SOTW suggestions, forwarded to mod-only threads.
- reminders.py => Weekly reminders by DM or in a channel, e.g. for the people posting the QOTW and SOTW.

### Reminders

- `/reminder timezone {timezone}` => set your timezone once (e.g. `Europe/Amsterdam`), required before adding reminders.
- `/reminder set {time} {day} {text} [channel]` => send `{text}` every `{day}` at `{time}` (24-hour `HH:MM`, in your timezone).
  Without `channel` it's sent as a DM; with `channel` it's posted there as `@you {text}`.
- `/reminder edit` => pick one of your reminders to edit (time, day, text, channel) or delete it.
  Clearing the channel turns it back into a DM reminder.

The `/reminder` commands are hidden by default. Allow the people who need them in
Server Settings -> Integrations -> bot -> `/reminder`. For DM reminders they need to allow DMs from server members.

Channel reminders can only target channels both the user and the bot can post in; this is checked when the
reminder is saved and again when it is sent. If the channel can't be used anymore, the reminder is sent as a DM
instead. Only user mentions in the text ping; `@everyone`, `@here` and role mentions don't.

### Database changes

The baseline schema is created in `database.py` (`SQL_CREATE_TABLES`) and is never edited. Every schema change
is a new `Migration` in `migrations.py` with the next version number. Migrations run automatically at startup;
the applied version is stored in the database itself (`PRAGMA user_version`). A failing migration is rolled back
and stops the bot from starting.

### Dependencies

The bot runs on a Raspberry Pi, which uses the system timezone database. Windows has no system timezone
database, so `tzdata` is only installed there.