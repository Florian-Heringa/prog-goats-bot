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
- reminders.py => Weekly DM reminders, e.g. for the people posting the QOTW and SOTW.

### Reminders

- `/reminder timezone {timezone}` => set your timezone once (e.g. `Europe/Amsterdam`), required before adding reminders.
- `/reminder set {time} {day} {text}` => DM `{text}` every `{day}` at `{time}` (24-hour `HH:MM`, in your timezone).
- `/reminder edit` => pick one of your reminders to edit or delete it.

The `/reminder` commands are hidden by default. Allow the people who need them in
Server Settings -> Integrations -> bot -> `/reminder`. They also need to allow DMs from server members.

### Dependencies

The bot runs on a Raspberry Pi, which uses the system timezone database. Windows has no system timezone
database, so `tzdata` is only installed there.