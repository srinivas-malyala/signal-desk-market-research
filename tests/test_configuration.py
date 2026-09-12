from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_never_selects_a_databricks_profile() -> None:
    text = (ROOT / "databricks.yml").read_text()
    assert "profile:" not in text


def test_development_target_uses_selected_unity_catalog_schema() -> None:
    text = (ROOT / "databricks.yml").read_text()
    assert "catalog: bootcamp_students" in text
    assert "schema: student_sri" in text
    assert "warehouse_id: b15d3d6f837ba428" in text
    assert "default: main" not in text
    assert "schema: signal_desk_dev" not in text
    assert "replace-before-deploy" not in text


def test_existing_unity_catalog_schema_is_not_bundle_managed() -> None:
    text = (ROOT / "resources" / "storage.yml").read_text()
    assert "schemas:" not in text
    assert "schema_name: ${var.schema}" in text


def test_apps_use_resource_references_instead_of_scope_names() -> None:
    for path in (ROOT / "mcp_server" / "app.yaml", ROOT / "dashboard" / "app.yaml"):
        text = path.read_text()
        assert "valueFrom:" in text
        assert "SECRET_SCOPE" not in text
        assert "DATABRICKS_WAREHOUSE_ID" in text
        assert "valueFrom: sql-warehouse" in text
        assert "SIGNAL_DESK_SCHEMA" in text
        assert "value: bootcamp_students" in text
        assert "SIGNAL_DESK_TABLE_SUFFIX" in text
        assert "value: srini" in text
        assert "SIGNAL_DESK_GRAPH_SCHEMA" in text
        assert "value: bootcamp_cdc" in text


def test_apps_attach_selected_warehouse_with_can_use() -> None:
    for path in (
        ROOT / "resources" / "stock_research_mcp.app.yml",
        ROOT / "resources" / "signal_desk_frontend.app.yml",
    ):
        text = path.read_text()
        assert "name: sql-warehouse" in text
        assert "id: ${var.warehouse_id}" in text
        assert "permission: CAN_USE" in text


def test_apps_attach_admin_managed_lakebase_secret() -> None:
    for path in (
        ROOT / "resources" / "stock_research_mcp.app.yml",
        ROOT / "resources" / "signal_desk_frontend.app.yml",
    ):
        text = path.read_text()
        assert "name: lakebase-url" in text
        assert "scope: database" in text
        assert "key: lakebase-url" in text
        assert "permission: READ" in text


def test_market_job_has_phase1_safety_controls() -> None:
    text = (ROOT / "resources" / "market_ingestion.job.yml").read_text()
    assert "max_concurrent_runs: 1" in text
    assert "name: start_date" in text
    assert "name: end_date" in text
    assert 'name: max_dates' in text
    assert 'default: "10"' in text
    assert "name: stop_after_row_estimate" in text
    assert "databricks-sdk>=0.81,<1" in text
    assert "requests>=2.32,<3" in text


def test_market_and_research_pipeline_resources_are_isolated() -> None:
    market = (ROOT / "resources" / "market_pipeline.pipeline.yml").read_text()
    research = (ROOT / "resources" / "research_pipeline.pipeline.yml").read_text()
    backfill = (ROOT / "resources" / "market_volume_backfill.job.yml").read_text()

    assert "include: ../pipelines/**" not in market + research
    assert "bronze_market_daily.py" in market
    assert "bronze_sec_submissions.py" not in market
    assert "bronze_sec_submissions.py" in research
    assert "bronze_market_daily.py" not in research
    assert "*.py" not in market + research
    assert 'spark.sql.caseSensitive: "true"' in market
    assert "${resources.pipelines.market_pipeline.id}" in backfill
    assert "${resources.pipelines.research_pipeline.id}" not in backfill


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


def test_serverless_python_entry_points_do_not_require_dunder_file() -> None:
    entry_points = (
        ROOT / "ingestion" / "market_backfill.py",
        ROOT / "ingestion" / "article_landing.py",
        ROOT / "ingestion" / "sec_landing.py",
        ROOT / "jobs" / "certify_market_volume.py",
        ROOT / "jobs" / "ingest_research_embeddings.py",
    )
    for path in entry_points:
        text = path.read_text()
        assert 'globals().get("filename")' in text, path
        assert "Path(__file__)" not in text, path
        assert "raise SystemExit(main())" not in text, path


def test_runtime_sql_contains_no_unqualified_operational_tables() -> None:
    tables = (
        "users|watchlists|watchlist_tickers|companies|price_snapshots|news_articles|"
        "research_notes|analysis_reports|research_embeddings|stock_research_mcp_traces"
    )
    pattern = re.compile(rf"\b(?:FROM|INTO|JOIN|UPDATE|USING)\s+(?:{tables})\b", re.IGNORECASE)
    for path in (
        ROOT / "dashboard" / "app.py",
        ROOT / "mcp_server" / "research_broker.py",
        ROOT / "mcp_server" / "stock_research_mcp_server.py",
        ROOT / "jobs" / "ingest_research_embeddings.py",
    ):
        assert not pattern.search(path.read_text()), path


def test_managed_research_search_resources_replace_in_process_embeddings() -> None:
    search = (ROOT / "resources" / "research_search.yml").read_text()
    sync_job = (ROOT / "resources" / "research_embeddings.job.yml").read_text()
    requirements = (ROOT / "mcp_server" / "requirements.txt").read_text()
    assert "endpoint_type: STANDARD" in search
    assert "index_type: DELTA_SYNC" in search
    assert "pipeline_type: TRIGGERED" in search
    assert "databricks-qwen3-embedding-0-6b" in search
    assert "chunk_to_embed" in search and "chunk_to_retrieve" in search
    assert "sync_research_index" in sync_job
    assert "sentence-transformers" not in requirements
