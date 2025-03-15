#!/bin/bash

# Script to update the Alembic env.py file and run migrations

echo "Updating Alembic configuration and running migrations..."

# Activate virtual environment
source venv/bin/activate

# Update the Alembic env.py file
cat > alembic/env.py << 'EOF'
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate support
from app.db.session import Base

# Import all models to ensure they are registered with Base.metadata
# Import models in the correct order to avoid circular dependencies
from app.models.tenant import Tenant, Role, Permission
from app.models.user import User
from app.models.app import File, Tag
from app.models.event import Event
from app.models.task import Task, TaskStep, SubTask, TaskStatus, RecurrenceType

# Set target metadata
target_metadata = Base.metadata

# optionally, you can read the DATABASE_URL from an environment variable
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", "sqlite:///./local_dev.db"))

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
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
EOF

# Create a new Alembic migration
echo -e "\nCreating a new Alembic migration..."
alembic revision --autogenerate -m "Update schema with all models"

# Apply the migration
echo -e "\nApplying the migration..."
alembic upgrade head

# Check the database schema
echo -e "\nChecking database schema for users table:"
psql postgresql://masteradmin:fastapidb@fastapi-db.c9c8eg0agu7x.ap-south-1.rds.amazonaws.com:5432/fastapi_db -c "\d users"

# Restart Gunicorn
echo -e "\nRestarting Gunicorn..."
sudo systemctl restart gunicorn

echo "Fix completed!" 