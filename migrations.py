"""
History of database schema changes for the ProgGOATs bot.

The baseline schema is created in 'database.py' (SQL_CREATE_TABLES) and is never edited.
Every schema change after that is added here as a new Migration with the next version number.
Migrations run automatically at startup; the applied version is stored in SQLite's 'PRAGMA user_version'.
"""
import aiosqlite
from dataclasses import dataclass

@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    statements: list[str]

MIGRATIONS: list[Migration] = [
    Migration(
        1,
        "Reminders: add channel_id (NULL = send as DM)",
        ["ALTER TABLE reminders ADD COLUMN channel_id INTEGER"],
    ),
]

async def get_schema_version(conn: aiosqlite.Connection) -> int:
    async with conn.execute("PRAGMA user_version") as cursor:
        row = await cursor.fetchone()
    return row[0] if row else 0

async def run_migrations(conn: aiosqlite.Connection, migrations: list[Migration] = MIGRATIONS):
    versions = [m.version for m in migrations]
    assert versions == list(range(1, len(migrations) + 1)), f"Migration versions must be 1, 2, 3, ... without gaps, got {versions}"

    current = await get_schema_version(conn)
    for migration in migrations:
        if migration.version <= current:
            continue

        # sqlite3 doesn't start transactions for DDL by itself, so begin explicitly to make each migration atomic
        try:
            await conn.execute("BEGIN")
            for statement in migration.statements:
                await conn.execute(statement)
            # PRAGMA doesn't accept parameters; the version is a validated int
            await conn.execute(f"PRAGMA user_version = {int(migration.version)}")
            await conn.commit()
        except Exception:
            await conn.rollback()
            print(f"Migration {migration.version} failed: {migration.description}")
            raise

        print(f"Applied migration {migration.version}: {migration.description}")
