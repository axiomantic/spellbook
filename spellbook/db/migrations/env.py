"""Alembic multi-database migration environment.

Supports all 4 spellbook databases. Use ``-x db=<name>`` to target
a specific database, or omit to run migrations against all databases.

Example usage::

    alembic -c spellbook/db/migrations/alembic.ini upgrade head
    alembic -c spellbook/db/migrations/alembic.ini -x db=fractal upgrade head
"""

import asyncio
from logging.config import fileConfig

from alembic import context

from spellbook.db.base import (
    CoordinationBase,
    ForgedBase,
    FractalBase,
    SpellbookBase,
)

# Import model modules so their tables are registered on the metadata
import spellbook.db.coordination_models  # noqa: F401
import spellbook.db.forged_models  # noqa: F401
import spellbook.db.fractal_models  # noqa: F401
import spellbook.db.spellbook_models  # noqa: F401

from spellbook.db.engines import (
    coordination_engine,
    forged_engine,
    fractal_engine,
    spellbook_engine,
)

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DB_CONFIGS = {
    "spellbook": {
        "engine": spellbook_engine,
        "metadata": SpellbookBase.metadata,
        "version_table": "alembic_version",
    },
    "fractal": {
        "engine": fractal_engine,
        "metadata": FractalBase.metadata,
        "version_table": "alembic_version",
    },
    "forged": {
        "engine": forged_engine,
        "metadata": ForgedBase.metadata,
        "version_table": "alembic_version",
    },
    "coordination": {
        "engine": coordination_engine,
        "metadata": CoordinationBase.metadata,
        "version_table": "alembic_version",
    },
}


def _get_target_db() -> str | None:
    """Get the target database from -x db=<name> CLI argument."""
    x_args = context.get_x_argument(as_dictionary=True)
    return x_args.get("db")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL scripts)."""
    target_db = _get_target_db()
    databases = [target_db] if target_db else list(DB_CONFIGS.keys())

    for db_name in databases:
        db_config = DB_CONFIGS[db_name]
        context.configure(
            url=str(db_config["engine"].url),
            target_metadata=db_config["metadata"],
            version_table=db_config["version_table"],
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
    """Run migrations in 'online' mode with async engines."""
    target_db = _get_target_db()
    databases = [target_db] if target_db else list(DB_CONFIGS.keys())

    for db_name in databases:
        db_config = DB_CONFIGS[db_name]
        engine = db_config["engine"]

        async with engine.connect() as connection:
            await connection.run_sync(
                do_run_migrations,
                db_config["metadata"],
                db_config["version_table"],
            )

        # Dispose engine after migration to release connections
        await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
