import aiosqlite
import time
from dataclasses import dataclass

from migrations import run_migrations

CONFIG_VALUE_DEFAULTS = {
    "WELCOME_CHANNEL": None,
    "NEW_MEMBER_ROLE_ID": None,
    "NEW_MEMBER_ROLE_DURATION": str(7 * 24 * 60 * 60),
    "GUILD_ID": str(708749383918944349),
    "SOTW_SUGGESTION_THREAD": None,
    "QOTW_SUGGESTION_THREAD": None,
    "SUGGESTION_COOLDOWN": str(60 * 60),
    "ADMIN_ROLE_IDS": "",
}

@dataclass
class Reminder:
    id: int
    user_id: int
    weekday: int        # 0 = monday
    time_of_day: str    # 'HH:MM' in the user's timezone
    text: str
    next_run: float     # unix timestamp
    channel_id: int | None = None  # None = send as DM

class PG_database():
    """
    Database connection and information for the ProGOATs bot
    """

    DB_NAME = "prog_goats_data.db"
    # Baseline schema: do NOT edit these statements.
    # Every schema change is added as a new Migration in 'migrations.py', so existing and fresh databases end up identical.
    SQL_CREATE_TABLES = [
        """
        CREATE TABLE IF NOT EXISTS config_values(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            key VARCHAR(100) UNIQUE, 
            value VARCHAR(100)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS temporary_roles(
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            remove_at TIMESTAMP NOT NULL,
            PRIMARY KEY (user_id, role_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS reminders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            time_of_day TEXT NOT NULL,
            text TEXT NOT NULL,
            next_run REAL NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS user_settings(
            user_id INTEGER PRIMARY KEY,
            timezone TEXT
        );
        """,
        ]
    SQL_REMINDER_COLUMNS = "id, user_id, weekday, time_of_day, text, next_run, channel_id"
    SQL_ALL_CONFIG_VALUES = """
        SELECT key, value FROM config_values
        """
    SQL_SET_CONFIG = """
        INSERT INTO config_values (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """

    def __init__(self):
        self.conn: aiosqlite.Connection | None = None 
        self._config_cache: dict[str, str] = {}

    #================================================================================
    # Configuration Cache methods

    async def _load_config_cache(self):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return
        
        async with self.conn.execute(self.SQL_ALL_CONFIG_VALUES) as cursor:
            rows = await cursor.fetchall()

        self._config_cache = {key: value for key, value in rows}

    def get_config_value(self, key: str, default: str | None = None) -> str | None:
        return self._config_cache.get(key, default)

    async def set_config_value(self, key: str, value: str):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return
        
        await self.conn.execute(self.SQL_SET_CONFIG, (key, value))
        await self.conn.commit()
        await self._load_config_cache()

    async def populate_defaults(self):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return
        
        for k, v in CONFIG_VALUE_DEFAULTS.items():
            await self.conn.execute("INSERT OR IGNORE INTO config_values (key, value) VALUES (?, ?)", (k, v))

        await self.conn.commit()
        await self._load_config_cache()


    #===================================================================================
    # Temporary Roles
    async def add_temp_role(self, user_id: int, role_id: int, guild_id: int, remove_in: int):
        """Takes in a user id, role id and a number describing the amount of seconds before the role should be removed again"""

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return
        
        remove_at = time.time() + remove_in
        await self.conn.execute(
            """INSERT INTO temporary_roles (user_id, role_id, guild_id, remove_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, role_id) DO UPDATE SET remove_at = excluded.remove_at, guild_id = excluded.guild_id
            """,
            (user_id, role_id, guild_id, remove_at)
        )
        await self.conn.commit()

    async def remove_temp_role(self, user_id: int, role_id: int):
        
        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return

        await self.conn.execute(
            """
            DELETE FROM temporary_roles WHERE user_id = ? AND role_id = ?
            """,
            (user_id, role_id)
        )

        await self.conn.commit()

    async def get_expired_temp_roles(self) -> list[tuple[int, int, int]] | None:

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return None
        
        async with self.conn.execute(
            "SELECT user_id, role_id, guild_id FROM temporary_roles WHERE remove_at <= ?",
            (time.time(), )
        ) as cursor:
            return await cursor.fetchall()

    #===================================================================================
    # Reminders
    # Reminder queries coming from a user are always filtered on user_id, so nobody can touch another user's reminder

    async def add_reminder(self, user_id: int, weekday: int, time_of_day: str, text: str, next_run: float, channel_id: int | None = None) -> int | None:

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return None

        cursor = await self.conn.execute(
            "INSERT INTO reminders (user_id, weekday, time_of_day, text, next_run, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, weekday, time_of_day, text, next_run, channel_id)
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def get_user_reminders(self, user_id: int) -> list[Reminder]:

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return []

        async with self.conn.execute(
            f"SELECT {self.SQL_REMINDER_COLUMNS} FROM reminders WHERE user_id = ? ORDER BY weekday, time_of_day",
            (user_id, )
        ) as cursor:
            return [Reminder(*row) for row in await cursor.fetchall()]

    async def get_reminder(self, user_id: int, reminder_id: int) -> Reminder | None:

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return None

        async with self.conn.execute(
            f"SELECT {self.SQL_REMINDER_COLUMNS} FROM reminders WHERE user_id = ? AND id = ?",
            (user_id, reminder_id)
        ) as cursor:
            row = await cursor.fetchone()
        return Reminder(*row) if row else None

    async def update_reminder(self, user_id: int, reminder_id: int, weekday: int, time_of_day: str, text: str, next_run: float, channel_id: int | None):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return

        await self.conn.execute(
            "UPDATE reminders SET weekday = ?, time_of_day = ?, text = ?, next_run = ?, channel_id = ? WHERE user_id = ? AND id = ?",
            (weekday, time_of_day, text, next_run, channel_id, user_id, reminder_id)
        )
        await self.conn.commit()

    async def delete_reminder(self, user_id: int, reminder_id: int):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return

        await self.conn.execute("DELETE FROM reminders WHERE user_id = ? AND id = ?", (user_id, reminder_id))
        await self.conn.commit()

    async def get_due_reminders(self, now: float) -> list[Reminder]:

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return []

        async with self.conn.execute(
            f"SELECT {self.SQL_REMINDER_COLUMNS} FROM reminders WHERE next_run <= ?",
            (now, )
        ) as cursor:
            return [Reminder(*row) for row in await cursor.fetchall()]

    async def set_reminder_next_run(self, reminder_id: int, next_run: float):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return

        await self.conn.execute("UPDATE reminders SET next_run = ? WHERE id = ?", (next_run, reminder_id))
        await self.conn.commit()

    #===================================================================================
    # User settings

    async def get_user_timezone(self, user_id: int) -> str | None:

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return None

        async with self.conn.execute("SELECT timezone FROM user_settings WHERE user_id = ?", (user_id, )) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def set_user_timezone(self, user_id: int, timezone: str):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return

        await self.conn.execute(
            """INSERT INTO user_settings (user_id, timezone) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET timezone = excluded.timezone
            """,
            (user_id, timezone)
        )
        await self.conn.commit()

    #===================================================================================
    # Context management

    async def connect(self):
        self.conn = await aiosqlite.connect(self.DB_NAME)
        for sql in self.SQL_CREATE_TABLES:
            await self.conn.execute(sql)
        await self.conn.commit()
        await run_migrations(self.conn)
        await self._load_config_cache()

    async def close(self):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return
        
        await self.conn.close()
