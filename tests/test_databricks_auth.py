from __future__ import annotations

from types import SimpleNamespace

import pytest

from shared import databricks_auth


def test_render_m2m_configuration_is_explicit_and_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGNAL_DESK_HOSTING", "render")
    monkeypatch.setenv("DATA_WORKSPACE_HOST", "https://workspace.example.test")
    monkeypatch.delenv("DATA_WORKSPACE_CLIENT_ID", raising=False)
    monkeypatch.delenv("DATA_WORKSPACE_CLIENT_SECRET", raising=False)
    with pytest.raises(databricks_auth.DatabricksAuthConfigurationError, match="not configured"):
        databricks_auth.databricks_config()

    monkeypatch.setenv("DATA_WORKSPACE_CLIENT_ID", "client-id-123")
    monkeypatch.setenv("DATA_WORKSPACE_CLIENT_SECRET", "secret-value-that-is-long-enough")
    captured = {}
    monkeypatch.setattr(
        databricks_auth,
        "Config",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(**kwargs),
    )
    config = databricks_auth.databricks_config()
    assert config.host == "https://workspace.example.test"
    assert config.client_id == "client-id-123"
    assert config.auth_type == "oauth-m2m"
    assert "client_secret" in captured


@pytest.mark.parametrize(
    "host",
    (
        "http://workspace.example.test",
        "https://user:pass@workspace.example.test",
        "https://workspace.example.test/a/path",
        "https://workspace.example.test?token=secret",
    ),
)
def test_render_workspace_host_must_be_a_clean_https_origin(
    monkeypatch: pytest.MonkeyPatch,
    host: str,
) -> None:
    monkeypatch.setenv("SIGNAL_DESK_HOSTING", "render")
    monkeypatch.setenv("DATA_WORKSPACE_HOST", host)
    monkeypatch.setenv("DATA_WORKSPACE_CLIENT_ID", "client-id-123")
    monkeypatch.setenv("DATA_WORKSPACE_CLIENT_SECRET", "secret-value-that-is-long-enough")
    with pytest.raises(databricks_auth.DatabricksAuthConfigurationError, match="HTTPS workspace origin"):
        databricks_auth.databricks_config()


def test_non_render_mode_preserves_ambient_config(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = SimpleNamespace(host="https://ambient.example.test")
    monkeypatch.setenv("SIGNAL_DESK_HOSTING", "local")
    monkeypatch.setattr(databricks_auth, "Config", lambda: sentinel)
    assert databricks_auth.databricks_config() is sentinel


def test_unknown_hosting_mode_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGNAL_DESK_HOSTING", "unexpected")
    with pytest.raises(databricks_auth.DatabricksAuthConfigurationError, match="invalid"):
        databricks_auth.hosting_mode()
