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