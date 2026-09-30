"""Minimal psycopg 3 Lakebase connector for Databricks serverless Jobs."""

from __future__ import annotations

import base64
import os
import re
import ssl
from contextlib import contextmanager
from typing import Any
from urllib.parse import unquote, urlparse

from databricks.sdk import WorkspaceClient

IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _identifier(value: str, setting: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{setting} must be a lowercase PostgreSQL identifier")
    return value


def quota_table() -> str:
    schema = _identifier(os.getenv("SIGNAL_DESK_SCHEMA", "bootcamp_students"), "SIGNAL_DESK_SCHEMA")
    suffix = _identifier(os.getenv("SIGNAL_DESK_TABLE_SUFFIX", "srini"), "SIGNAL_DESK_TABLE_SUFFIX")
    return f"{schema}.massive_api_attempts_{suffix}"


def lakebase_url(profile: str | None = None) -> str:
    if os.getenv("LAKEBASE_URL"):
        return os.environ["LAKEBASE_URL"]
    workspace = WorkspaceClient(profile=profile) if profile else WorkspaceClient()
    secret = workspace.secrets.get_secret(
        scope=os.getenv("LAKEBASE_SECRET_SCOPE", "database"),
        key=os.getenv("LAKEBASE_SECRET_KEY", "lakebase-url"),
    )
    return base64.b64decode(secret.value).decode("utf-8")


@contextmanager
def connection(*, profile: str | None = None) -> Any:
    """Yield one pure-Python DB-API connection without native libpq imports."""
    import pg8000.dbapi

    parsed = urlparse(lakebase_url(profile))
    if parsed.scheme not in {"postgres", "postgresql"} or not all(
        (parsed.hostname, parsed.username, parsed.password, parsed.path.lstrip("/"))
    ):
        raise ValueError("Lakebase URL must be a complete PostgreSQL connection URL")
    database = pg8000.dbapi.connect(
        user=unquote(parsed.username),
        password=unquote(parsed.password),
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip("/"),
        timeout=10,
        application_name="signal-desk-databricks-job",
        ssl_context=ssl.create_default_context(),
    )
    try:
        yield database
    finally:
        database.close()
