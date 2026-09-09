import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# app/db/alembic/env.py -> repo root is three parents up. Alembic runs this
# file directly (not as part of the `app` package), so the repo root needs to
# be on sys.path before `import app...` below will resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.db.database import _resolve_database_url  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import every model module so SQLModel.metadata is fully populated before
# autogenerate compares it against the database — mirrors app.db.database.init_db().
import app.db.models  # noqa: E402,F401
from sqlmodel import SQLModel  # noqa: E402

target_metadata = SQLModel.metadata

# Resolve DATABASE_URL the same way the running app does (same
# postgres:// -> postgresql:// normalisation), overriding whatever
# alembic.ini's sqlalchemy.url is set to (it is left unset there on purpose).
config.set_main_option("sqlalchemy.url", _resolve_database_url())


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
