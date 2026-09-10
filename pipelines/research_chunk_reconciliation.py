"""Assert chunk uniqueness and complete source provenance."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="research_chunk_reconciliation",
    comment="Single-row uniqueness and provenance evidence for all retrieval chunks.",
)
@dp.expect_all_or_fail(
    {
        "chunk_ids_unique": "duplicate_chunk_ids = 0",
        "chunk_indexes_unique_per_source": "duplicate_source_indexes = 0",
        "all_chunks_traceable": "untraceable_chunks = 0",
    }
)
def research_chunk_reconciliation():
    chunks = spark.read.table("silver_research_chunks")  # noqa: F821 - injected by Databricks SDP
    duplicate_ids = chunks.groupBy("chunk_id").count().filter(F.col("count") > 1)
    duplicate_indexes = chunks.groupBy("source_type", "source_id", "chunk_index").count().filter(
        F.col("count") > 1
    )
    untraceable = chunks.filter(
        F.col("source_url").isNull()
        | F.col("source_id").isNull()
        | F.col("chunk_content_hash").isNull()
        | F.col("source_content_hash").isNull()
    )
    return (
        chunks.agg(F.count("*").alias("chunk_count"), F.countDistinct("source_id").alias("source_count"))
        .crossJoin(duplicate_ids.agg(F.count("*").alias("duplicate_chunk_ids")))
        .crossJoin(duplicate_indexes.agg(F.count("*").alias("duplicate_source_indexes")))
        .crossJoin(untraceable.agg(F.count("*").alias("untraceable_chunks")))
        .withColumn("checked_at", F.current_timestamp())
    )
