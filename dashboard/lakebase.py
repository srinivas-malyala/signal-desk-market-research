"""Pooled Lakebase read/write helper for the separately deployed dashboard."""

import base64
import os
import re
import threading
from contextlib import contextmanager

from databricks.sdk import WorkspaceClient
from psycopg2 import InterfaceError, OperationalError, pool
from psycopg2.extras import RealDictCursor

DEFAULT_SCHEMA = "bootcamp_students"
DEFAULT_GRAPH_SCHEMA = "bootcamp_cdc"
DEFAULT_TABLE_SUFFIX = "srini"
IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
TABLE_BASES = frozenset(
    {
        "analysis_reports",
        "companies",
        "news_articles",
        "price_snapshots",
        "research_notes",
        "stock_research_mcp_traces",
        "users",
        "watchlist_tickers",
        "watchlists",
    }
)

_pool: pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _identifier(value: str, setting: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{setting} must be a lowercase PostgreSQL identifier")
    return value


def schema_name() -> str:
    return _identifier(os.getenv("SIGNAL_DESK_SCHEMA", DEFAULT_SCHEMA), "SIGNAL_DESK_SCHEMA")


def graph_schema_name() -> str:
    return _identifier(
        os.getenv("SIGNAL_DESK_GRAPH_SCHEMA", DEFAULT_GRAPH_SCHEMA),
        "SIGNAL_DESK_GRAPH_SCHEMA",
    )


def table_suffix() -> str:
    return _identifier(
        os.getenv("SIGNAL_DESK_TABLE_SUFFIX", DEFAULT_TABLE_SUFFIX),
        "SIGNAL_DESK_TABLE_SUFFIX",
    )


def table_name(base_table: str) -> str:
    if base_table not in TABLE_BASES:
        raise ValueError(f"Unknown Signal Desk table: {base_table!r}")
    return f"{schema_name()}.{base_table}_{table_suffix()}"


def configure_schema(conn) -> None:
    required = (schema_name(), graph_schema_name())
    with conn.cursor() as cur:
        cur.execute("SELECT nspname FROM pg_namespace WHERE nspname = ANY(%s)", (list(required),))
        present = {row["nspname"] for row in cur.fetchall()}
        missing = sorted(set(required) - present)
        if missing:
            raise RuntimeError(f"Required Lakebase schema(s) do not exist: {', '.join(missing)}")


def url() -> str:
    if os.getenv("LAKEBASE_URL"):
        return os.environ["LAKEBASE_URL"]
    value = WorkspaceClient().secrets.get_secret(
        scope=os.getenv("LAKEBASE_SECRET_SCOPE", "database"),
        key=os.getenv("LAKEBASE_SECRET_KEY", "lakebase-url"),
    )
    return base64.b64decode(value.value).decode("utf-8")


def get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                minimum = int(os.getenv("LAKEBASE_POOL_MIN", "1"))
                maximum = int(os.getenv("LAKEBASE_POOL_MAX", "5"))
                if minimum < 1 or maximum < minimum or maximum > 20:
                    raise ValueError("Lakebase pool bounds must satisfy 1 <= min <= max <= 20")
                _pool = pool.ThreadedConnectionPool(
                    minimum,
                    maximum,
                    dsn=url(),
                    cursor_factory=RealDictCursor,
                    connect_timeout=10,
                    application_name="signal-desk-dashboard",
                )
    return _pool


def _checkout(connection_pool: pool.ThreadedConnectionPool):
    conn = connection_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except (InterfaceError, OperationalError):
        connection_pool.putconn(conn, close=True)
        conn = connection_pool.getconn()
    return conn


@contextmanager
def connection():
    connection_pool = get_pool()
    conn = _checkout(connection_pool)
    try:
        configure_schema(conn)
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn, close=bool(conn.closed))


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
