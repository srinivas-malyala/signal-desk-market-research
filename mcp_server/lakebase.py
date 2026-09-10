"""Lakebase access and migration helpers for the stock research app."""

from __future__ import annotations

import base64
import os
import re
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor

DEFAULT_SCHEMA = "student_sri"
SCHEMA_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


def get_schema_name() -> str:
    """Return the isolated application schema after validating its identifier."""
    schema = os.getenv("SIGNAL_DESK_SCHEMA", DEFAULT_SCHEMA)
    if not SCHEMA_PATTERN.fullmatch(schema):
        raise ValueError("SIGNAL_DESK_SCHEMA must be a lowercase PostgreSQL identifier")
    return schema


def configure_schema(connection) -> None:
    """Require the provisioned schema and make it the session's first lookup path."""
    schema = get_schema_name()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = %s) AS schema_exists",
            (schema,),
        )
        if not cursor.fetchone()["schema_exists"]:
            raise RuntimeError(f"Required Lakebase schema {schema!r} does not exist")
        cursor.execute(
            "SELECT set_config('search_path', %s, false)",
            (f"{schema},public",),
        )


def get_lakebase_url() -> str:
    if os.getenv("LAKEBASE_URL"):
        return os.environ["LAKEBASE_URL"]
    secret = WorkspaceClient().secrets.get_secret(
        scope=os.getenv("LAKEBASE_SECRET_SCOPE", "database"),
        key=os.getenv("LAKEBASE_SECRET_KEY", "lakebase-url"),
    )
    return base64.b64decode(secret.value).decode("utf-8")


@contextmanager
def get_connection():
    connection = psycopg2.connect(get_lakebase_url(), cursor_factory=RealDictCursor)
    try:
        configure_schema(connection)
        yield connection
    finally:
        connection.close()


def query(sql: str, params=None) -> list[dict]:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def write(sql: str, params=None, returning: bool = False):
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        value = dict(cursor.fetchone()) if returning else cursor.rowcount
        connection.commit()
        return value


def migrate() -> None:
    migration_sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(migration_sql)
        connection.commit()
