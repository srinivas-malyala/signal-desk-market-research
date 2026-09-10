"""Read/write helper for the separately deployed dashboard app."""

import base64
import os
import re
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor

DEFAULT_SCHEMA = "student_sri"
SCHEMA_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


def schema_name():
    schema = os.getenv("SIGNAL_DESK_SCHEMA", DEFAULT_SCHEMA)
    if not SCHEMA_PATTERN.fullmatch(schema):
        raise ValueError("SIGNAL_DESK_SCHEMA must be a lowercase PostgreSQL identifier")
    return schema


def configure_schema(conn):
    schema = schema_name()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = %s) AS schema_exists",
            (schema,),
        )
        if not cur.fetchone()["schema_exists"]:
            raise RuntimeError(f"Required Lakebase schema {schema!r} does not exist")
        cur.execute(
            "SELECT set_config('search_path', %s, false)",
            (f"{schema},public",),
        )


def url():
    if os.getenv("LAKEBASE_URL"):
        return os.environ["LAKEBASE_URL"]
    value = WorkspaceClient().secrets.get_secret(
        scope=os.getenv("LAKEBASE_SECRET_SCOPE", "database"),
        key=os.getenv("LAKEBASE_SECRET_KEY", "lakebase-url"),
    )
    return base64.b64decode(value.value).decode()


@contextmanager
def connection():
    conn = psycopg2.connect(url(), cursor_factory=RealDictCursor)
    try:
        configure_schema(conn)
        yield conn
    finally:
        conn.close()


def query(sql, params=None):
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def write(sql, params=None, returning=False):
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        value = dict(cur.fetchone()) if returning else cur.rowcount
        conn.commit()
        return value
