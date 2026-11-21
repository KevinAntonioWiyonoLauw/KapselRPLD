"""Alembic environment.

Uses the application's declarative metadata (``app.db.session.Base`` + all models
registered via ``app.models``) as the source of truth for autogeneration, and the
runtime ``DATABASE_URL`` from app settings.

Supports running against a caller-provided connection (``config.attributes``
["connection"]) so ``init_db`` can serialize concurrent migrations with a Postgres
advisory lock held on that same connection.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db.session import Base
import app.models  # noqa: F401  (register all models on Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    shared = config.attributes.get("connection", None)
    if shared is not None:
        _run(shared)
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
