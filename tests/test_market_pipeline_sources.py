"""Static contract tests for pipeline files that execute only on Databricks Spark."""

from __future__ import annotations

import ast
from pathlib import Path

PIPELINES = Path(__file__).parents[1] / "pipelines"


def _source(name: str) -> str:
    source = (PIPELINES / name).read_text(encoding="utf-8")
    ast.parse(source)
    return source


def test_bronze_response_uses_modern_sdp_autoloader_and_lineage() -> None:
    source = _source("bronze_market_daily.py")

    assert "from pyspark import pipelines as dp" in source
    assert '.format("cloudFiles")' in source
    assert '"_metadata.file_path"' in source
    assert "input_file_name" not in source
    assert "import dlt" not in source
    assert 'pathGlobFilter", "response.json"' in source


def test_bronze_manifest_and_reconciliation_contracts_are_present() -> None:
    manifest_source = _source("bronze_market_manifests.py")
    reconciliation_source = _source("market_ingestion_reconciliation.py")

    assert 'pathGlobFilter", "manifest.json"' in manifest_source
    assert "manifest_matches_bronze" in reconciliation_source
    assert "manifest_row_count" in reconciliation_source
    assert "bronze_row_count" in reconciliation_source


def test_each_bronze_dataset_has_exactly_one_definition() -> None:
    for filename in (
        "bronze_market_daily.py",
        "bronze_market_manifests.py",
        "market_ingestion_reconciliation.py",
    ):
        tree = ast.parse((PIPELINES / filename).read_text(encoding="utf-8"))
        definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert len(definitions) == 1


def test_silver_routes_all_rows_to_accepted_or_quarantine() -> None:
    accepted = _source("silver_market_bars.py")
    quarantine = _source("silver_market_quarantine.py")
    reconciliation = _source("silver_market_reconciliation.py")

    assert 'F.col("quality_reason").isNull() & (F.col("dedupe_rank") == 1)' in accepted
    assert 'F.col("quality_reason").isNotNull() | (F.col("dedupe_rank") > 1)' in quarantine
    assert "bronze_rows = silver_rows + quarantine_rows" in reconciliation
    assert "duplicate_silver_keys = 0" in reconciliation


def test_silver_classification_prefers_valid_record_before_latest_duplicate() -> None:
    source = _source("market_bars_classified.py")

    quality_order = source.index('F.when(F.col("quality_reason").isNull()')
    recency_order = source.index('F.col("ingested_at").desc()')
    assert quality_order < recency_order
    assert 'Window.partitionBy("ticker_raw", "trading_date")' in source


def test_gold_metrics_have_stable_window_and_benchmark_definitions() -> None:
    performance = _source("gold_stock_performance.py")
    peers = _source("gold_market_peer_comparison.py")
    coverage = _source("gold_market_data_coverage.py")

    assert "rowsBetween(-19, 0)" in performance
    assert "F.stddev_samp" in performance
    assert "sqrt(252)" in performance
    assert "percentile_approx(daily_return, 0.5, 10000)" in peers
    assert "F.percent_rank" in peers
    assert 'F.lit("COMPLETE")' in coverage
