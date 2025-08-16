#!/usr/bin/env python3
"""
Script to check database state and reset if needed.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from sqlalchemy import text

    from packages.common.dental_backend_common.config import get_settings
    from packages.common.dental_backend_common.session import create_engine
except ImportError:
    # Fallback for when the modules are not available
    get_settings = None
    create_engine = None
    text = None


def check_database_state():
    """Check what exists in the database."""
    settings = get_settings()
    engine = create_engine(settings.database.url)

    with engine.connect() as conn:
        # Check if enums exist
        result = conn.execute(
            text(
                """
            SELECT typname FROM pg_type
            WHERE typname IN ('userrole', 'jobstatus', 'filestatus', 'segmenttype', 'modeltype', 'auditeventtype')
        """
            )
        )
        existing_enums = [row[0] for row in result.fetchall()]
        print(f"Existing enums: {existing_enums}")

        # Check if tables exist
        result = conn.execute(
            text(
                """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN ('users', 'cases', 'files', 'jobs', 'segments', 'models', 'audit_logs')
        """
            )
        )
        existing_tables = [row[0] for row in result.fetchall()]
        print(f"Existing tables: {existing_tables}")

        # Check alembic version
        try:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.scalar()
            print(f"Current Alembic version: {current_version}")
        except Exception as e:
            print(f"Alembic version table not found: {e}")
            current_version = None

    return existing_enums, existing_tables, current_version


def reset_database():
    """Reset the database completely."""
    settings = get_settings()
    engine = create_engine(settings.database.url)

    with engine.connect() as conn:
        # Drop all tables first
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        conn.commit()
        print("Database reset complete")


if __name__ == "__main__":
    print("Checking database state...")
    enums, tables, version = check_database_state()

    if enums or tables:
        print("\nDatabase has existing objects. Do you want to reset it? (y/n)")
        response = input().lower().strip()
        if response == "y":
            reset_database()
            print("Database reset. You can now run 'make migrate'")
        else:
            print(
                "Database not reset. You may need to manually clean up existing objects."
            )
    else:
        print("Database is clean. You can run 'make migrate'")
