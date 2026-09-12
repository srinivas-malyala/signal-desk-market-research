"""Lakebase access, namespacing, pooling, and migration helpers."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path

from databricks.sdk import WorkspaceClient
from psycopg2 import InterfaceError, OperationalError, pool
from psycopg2.extras import RealDictCursor

DEFAULT_SCHEMA = "bootcamp_students"
DEFAULT_GRAPH_SCHEMA = "bootcamp_cdc"
DEFAULT_TABLE_SUFFIX = "srini"
IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
MIGRATION_TOKEN = re.compile(r"\{\{(table|index):([a-z_][a-z0-9_]*)\}\}")

TABLE_BASES = frozenset(
    {
        "analysis_reports",
        "agent_sessions",
        "agent_tool_events",
        "companies",
        "idempotency_records",
        "news_articles",
        "news_article_tickers",
        "price_snapshots",
        "research_embeddings",
        "research_notes",
        "schema_migrations",
        "stock_research_mcp_traces",
        "users",
        "watchlist_tickers",
        "watchlists",
    }
)
INDEX_BASES = frozenset(
    {
        "idx_agent_events_time",
        "idx_news_ticker_time",
        "idx_news_article_tickers_ticker",
        "idx_price_ticker_time",
        "idx_research_embeddings_hnsw",
        "idx_research_embeddings_ticker",
        "idx_stock_trace_time",
    }
)

_pool: pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _identifier(value: str, setting: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{setting} must be a lowercase PostgreSQL identifier")
    return value


def get_schema_name() -> str:
    return _identifier(os.getenv("SIGNAL_DESK_SCHEMA", DEFAULT_SCHEMA), "SIGNAL_DESK_SCHEMA")


def get_graph_schema_name() -> str:
    return _identifier(
        os.getenv("SIGNAL_DESK_GRAPH_SCHEMA", DEFAULT_GRAPH_SCHEMA),
        "SIGNAL_DESK_GRAPH_SCHEMA",
    )


def get_table_suffix() -> str:
    return _identifier(
        os.getenv("SIGNAL_DESK_TABLE_SUFFIX", DEFAULT_TABLE_SUFFIX),
        "SIGNAL_DESK_TABLE_SUFFIX",
    )


def table_name(base_table: str, *, graph: bool = False) -> str:
    """Return an allowlisted, fully-qualified per-student table identifier."""
    if base_table not in TABLE_BASES:
        raise ValueError(f"Unknown Signal Desk table: {base_table!r}")
    schema = get_graph_schema_name() if graph else get_schema_name()
    return f"{schema}.{base_table}_{get_table_suffix()}"


def index_name(base_index: str) -> str:
    if base_index not in INDEX_BASES:
        raise ValueError(f"Unknown Signal Desk index: {base_index!r}")
    # PostgreSQL creates the index in its table's schema and rejects a
    # schema-qualified index name in CREATE INDEX.
    return f"{base_index}_{get_table_suffix()}"


def render_migration(template: str) -> str:
    """Render only allowlisted table/index tokens in a migration template."""

    def replace(match: re.Match[str]) -> str:
        kind, base = match.groups()
        return table_name(base) if kind == "table" else index_name(base)

    rendered = MIGRATION_TOKEN.sub(replace, template)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("Migration contains an unknown template token")
    return rendered


def configure_schema(connection) -> None:
    """Require the administrator-managed shared schemas; never create them."""
    required = (get_schema_name(), get_graph_schema_name())
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname = ANY(%s)",
            (list(required),),
        )
        present = {row["nspname"] for row in cursor.fetchall()}
        missing = sorted(set(required) - present)
        if missing:
            raise RuntimeError(f"Required Lakebase schema(s) do not exist: {', '.join(missing)}")
        cursor.execute("SELECT set_config('search_path', %s, false)", (f"{required[0]},public",))


def get_lakebase_url() -> str:
    """Return the URL from an explicit local override or the admin-managed secret."""
    if os.getenv("LAKEBASE_URL"):
        return os.environ["LAKEBASE_URL"]
    secret = WorkspaceClient().secrets.get_secret(
        scope=os.getenv("LAKEBASE_SECRET_SCOPE", "database"),
        key=os.getenv("LAKEBASE_SECRET_KEY", "lakebase-url"),
    )
    return base64.b64decode(secret.value).decode("utf-8")


def _pool_bounds() -> tuple[int, int]:
    minimum = int(os.getenv("LAKEBASE_POOL_MIN", "1"))
    maximum = int(os.getenv("LAKEBASE_POOL_MAX", "5"))
    if minimum < 1 or maximum < minimum or maximum > 20:
        raise ValueError("Lakebase pool bounds must satisfy 1 <= min <= max <= 20")
    return minimum, maximum


def get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                minimum, maximum = _pool_bounds()
                _pool = pool.ThreadedConnectionPool(
                    minimum,
                    maximum,
                    dsn=get_lakebase_url(),
                    cursor_factory=RealDictCursor,
                    connect_timeout=10,
                    application_name="signal-desk",
                )
    return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


def _checkout(connection_pool: pool.ThreadedConnectionPool):
    """Return a live pooled connection, replacing one stale connection once."""
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except (InterfaceError, OperationalError):
        connection_pool.putconn(connection, close=True)
        connection = connection_pool.getconn()
    return connection


@contextmanager
def get_connection():
    connection_pool = get_pool()
    connection = _checkout(connection_pool)
    try:
        configure_schema(connection)
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection_pool.putconn(connection, close=bool(connection.closed))


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


def migration_paths() -> list[Path]:
    return sorted((Path(__file__).with_name("migrations")).glob("[0-9][0-9][0-9][0-9]_*.sql"))


def migrate() -> list[str]:
    """Apply checksum-protected migrations once and return newly applied versions."""
    paths = migration_paths()
    if not paths:
        raise RuntimeError("No Lakebase migrations were found")
    migrations_table = table_name("schema_migrations")
    applied_now: list[str] = []
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {migrations_table} ("
            "version TEXT PRIMARY KEY, checksum_sha256 TEXT NOT NULL, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        cursor.execute(f"SELECT version, checksum_sha256 FROM {migrations_table}")
        applied = {row["version"]: row["checksum_sha256"] for row in cursor.fetchall()}
        for path in paths:
            version = path.name.split("_", 1)[0]
            template = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(template.encode("utf-8")).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(f"Applied Lakebase migration {version} has changed")
                continue
            cursor.execute(render_migration(template))
            cursor.execute(
                f"INSERT INTO {migrations_table}(version, checksum_sha256) VALUES(%s, %s)",
                (version, checksum),
            )
            applied_now.append(version)
        connection.commit()
    return applied_now
