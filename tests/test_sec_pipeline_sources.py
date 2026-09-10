from __future__ import annotations

import ast
from pathlib import Path

PIPELINES = Path(__file__).parents[1] / "pipelines"


def source(filename: str) -> str:
    value = (PIPELINES / filename).read_text(encoding="utf-8")
    ast.parse(value)
    return value


def test_sec_bronze_uses_modern_autoloader_and_content_address_lineage() -> None:
    for filename in ("bronze_sec_manifests.py", "bronze_sec_submissions.py", "bronze_sec_company_facts.py"):
        value = source(filename)
        assert "from pyspark import pipelines as dp" in value
        assert '.format("cloudFiles")' in value
        assert '"_metadata.file_path"' in value
        assert "input_file_name" not in value
        assert "import dlt" not in value
    assert "checksum=([a-f0-9]{64})" in source("bronze_sec_company_facts.py")


def test_sec_silver_has_deterministic_dedup_and_integrity_checks() -> None:
    facts = source("silver_sec_facts.py")
    filings = source("silver_sec_filings.py")
    reconciliation = source("sec_structured_reconciliation.py")
    assert "Window.partitionBy" in facts
    assert 'F.col("value_text").desc()' in facts
    assert 'Window.partitionBy("accession_number")' in filings
    assert "orphan_filing_ciks = 0 AND orphan_fact_ciks = 0" in reconciliation
    assert "duplicate_fact_keys = 0" in reconciliation


def test_industry_peer_dataset_uses_sec_reference_without_dropping_market_gold() -> None:
    value = source("gold_industry_peer_comparison.py")
    assert 'spark.read.table("gold_stock_performance")' in value
    assert 'spark.read.table("silver_sec_companies")' in value
    assert 'Window.partitionBy("industry", "trading_date")' in value


def test_article_bridge_preserves_many_to_many_ticker_relationships() -> None:
    bronze = source("bronze_research_articles.py")
    articles = source("silver_research_articles.py")
    bridge = source("silver_article_tickers.py")
    assert 'F.col("article.tickers").alias("tickers")' in bronze
    assert 'Window.partitionBy("article_id")' in articles
    assert 'F.explode("tickers")' in bridge
    assert '.dropDuplicates(["article_id", "ticker"])' in bridge
