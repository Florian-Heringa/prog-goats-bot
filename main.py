import os
print(os.getcwd())
from dotenv import load_dotenv
load_dotenv()

bot_token = str(os.getenv("BOT_TOKEN"))
debug_guild = int(os.getenv("DEBUG_GUILD")) # type: ignore

# =============================================================
import discord
from database import PG_database

class PG_Bot(discord.Bot):

    COGS_LIST = [
        'base',
        'config',
        'listening_party',
        'tasks',
        'admin',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db: PG_database = PG_database()

    async def start(self, *args, **kwargs):
        await self.db.connect()
        await self.db.populate_defaults()
        for cog in self.COGS_LIST:
            bot.load_extension(f"cogs.{cog}")
        await super().start(*args, **kwargs)

    async def close(self):
        await self.db.close()
        await super().close()

#============================================================

bot = PG_Bot(
    intents = discord.Intents.all(),
    debug_guilds = [debug_guild],
    owner_id=703546553125568545
)
bot.db = PG_database()
bot.run(bot_token)