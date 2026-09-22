import aiosqlite
import time

CONFIG_VALUE_DEFAULTS = {
    "WELCOME_CHANNEL": None,
    "NEW_MEMBER_ROLE_ID": None,
    "NEW_MEMBER_ROLE_DURATION": str(7 * 24 * 60 * 60),
    "GUILD_ID": str(708749383918944349),
}

class PG_database():
    """
    Database connection and information for the ProGOATs bot
    """

    DB_NAME = "prog_goats_data.db"
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
        ]
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
    # Context management

    async def connect(self):
        self.conn = await aiosqlite.connect(self.DB_NAME)
        for sql in self.SQL_CREATE_TABLES:
            await self.conn.execute(sql)
        await self.conn.commit()
        await self._load_config_cache()

    async def close(self):

        if not isinstance(self.conn, aiosqlite.Connection):
            print("Not connected to database")
            return
        
        await self.conn.close()
