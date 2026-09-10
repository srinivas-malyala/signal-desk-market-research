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
