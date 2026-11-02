from alembic import context
from sqlalchemy import engine_from_config, pool, Float
from app.config import settings
from app.db import Base
from app import models
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
def compare_types(ctx, inspected_column, metadata_column, inspected_type, metadata_type):
    # SQLite gives FLOAT/DOUBLE the same REAL affinity; SQLAlchemy 2.1 may infer
    # Double for Python float while historical migrations use Float. Do not
    # report this alias as a schema change. PostgreSQL uses normal comparison.
    if ctx.dialect.name == "sqlite" and isinstance(inspected_type, Float) and isinstance(metadata_type, Float):
        return False
    return None

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=compare_types)
        with context.begin_transaction():
            context.run_migrations()
