"""Explicit, fail-closed Databricks authentication for off-platform services."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config


class DatabricksAuthConfigurationError(RuntimeError):
    """Databricks credentials or target configuration are incomplete."""


def hosting_mode() -> str:
    mode = os.getenv("SIGNAL_DESK_HOSTING", "databricks").strip().casefold()
    if mode not in {"databricks", "local", "render"}:
        raise DatabricksAuthConfigurationError("SIGNAL_DESK_HOSTING is invalid.")
    return mode


def _workspace_host() -> str:
    raw = os.getenv("DATA_WORKSPACE_HOST", "").strip().rstrip("/")
    parsed = urlparse(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise DatabricksAuthConfigurationError("DATA_WORKSPACE_HOST must be an HTTPS workspace origin.")
    return raw


def databricks_config() -> Config:
    """Return ambient Databricks auth or explicit Render OAuth M2M auth."""

    if hosting_mode() != "render":
        return Config()
    host = _workspace_host()
    client_id = os.getenv("DATA_WORKSPACE_CLIENT_ID", "").strip()
    client_secret = os.getenv("DATA_WORKSPACE_CLIENT_SECRET", "").strip()
    if not 8 <= len(client_id) <= 256 or not 16 <= len(client_secret) <= 4096:
        raise DatabricksAuthConfigurationError("Paid-workspace OAuth M2M credentials are not configured.")
    return Config(
        host=host,
        client_id=client_id,
        client_secret=client_secret,
        auth_type="oauth-m2m",
    )


def workspace_client() -> WorkspaceClient:
    return WorkspaceClient(config=databricks_config())


def sql_connection(warehouse_id: str):
    """Create a SQL Warehouse connection without exposing an access token."""

    from databricks import sql

    config = databricks_config()
    return sql.connect(
        server_hostname=config.host.removeprefix("https://").removeprefix("http://"),
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        credentials_provider=lambda: config.authenticate,
    )
