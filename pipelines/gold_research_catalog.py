"""Publish one inspectable catalog record per filing or article research source."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_research_catalog",
    comment="Searchable filing/article catalog with tickers, dates, freshness, provenance, and chunk counts.",
    cluster_by=["source_type", "source_date"],
)
@dp.expect_all_or_fail(
    {
        "source_identity_present": "source_id IS NOT NULL",
        "source_url_present": "source_url RLIKE '^https?://'",
        "content_hash_present": "source_content_hash RLIKE '^[a-f0-9]{64}$'",
        "chunks_present": "chunk_count > 0",
    }
)
def gold_research_catalog():
    chunks = spark.read.table("silver_research_chunks")  # noqa: F821 - injected by Databricks SDP
    return chunks.groupBy(
        "source_type",
        "source_id",
        "tickers",
        "ticker",
        "title",
        "source_date",
        "source_url",
        "fetched_at",
        "source_content_hash",
    ).agg(
        F.count("*").alias("chunk_count"),
        F.sum(F.length("chunk_text")).alias("indexed_character_count"),
        F.max("chunk_index").alias("maximum_chunk_index"),
    )
