from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_never_selects_a_databricks_profile() -> None:
    text = (ROOT / "databricks.yml").read_text()
    assert "profile:" not in text


def test_apps_use_resource_references_instead_of_scope_names() -> None:
    for path in (ROOT / "mcp_server" / "app.yaml", ROOT / "dashboard" / "app.yaml"):
        text = path.read_text()
        assert "valueFrom:" in text
        assert "SECRET_SCOPE" not in text


def test_secret_setup_requires_an_explicit_profile() -> None:
    text = (ROOT / "setup_secrets.py").read_text()
    assert 'parser.add_argument("--profile", required=True' in text
    assert "WorkspaceClient(profile=args.profile)" in text


def test_configuration_contains_no_literal_credentials() -> None:
    candidates = [ROOT / "databricks.yml", *sorted((ROOT / "resources").glob("*.yml"))]
    prohibited = ("dapi", "postgresql://", "api_key:")
    for path in candidates:
        lowered = path.read_text().lower()
        assert not any(token.lower() in lowered for token in prohibited), path
