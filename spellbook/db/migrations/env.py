"""Alembic migration environment for spellbook database.

Example usage::

    alembic -c spellbook/db/migrations/alembic.ini upgrade head
"""

import asyncio
from logging.config import fileConfig

from alembic import context

from spellbook.db.base import SpellbookBase

# Import model modules so their tables are registered on the metadata
import spellbook.db.spellbook_models  # noqa: F401

from spellbook.db.engines import spellbook_engine

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DB_CONFIG = {
    "engine": spellbook_engine,
    "metadata": SpellbookBase.metadata,
    "version_table": "alembic_version",
}


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL scripts)."""
    context.configure(
        url=str(DB_CONFIG["engine"].url),
        target_metadata=DB_CONFIG["metadata"],
        version_table=DB_CONFIG["version_table"],
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection, metadata, version_table):
    """Run migrations for a single database connection."""
    context.configure(
        connection=connection,
        target_metadata=metadata,
        version_table=version_table,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    async with DB_CONFIG["engine"].connect() as connection:
        await connection.run_sync(
            do_run_migrations,
            DB_CONFIG["metadata"],
            DB_CONFIG["version_table"],
        )
    await DB_CONFIG["engine"].dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
