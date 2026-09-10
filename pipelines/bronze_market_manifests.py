"""Incrementally ingest Phase 1 landing manifests for audit and reconciliation."""

from _market_pipeline_common import MARKET_MANIFEST_SCHEMA, raw_market_path
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(
    name="bronze_market_manifests",
    comment="Immutable Massive response manifests used for completeness and rate-limit evidence.",
    cluster_by=["trading_date"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "manifest_version_supported": "version = 1",
        "manifest_source_supported": "source = 'massive' AND dataset = 'grouped_daily'",
        "manifest_successful": "status_code = 200",
        "manifest_counts_valid": "row_count >= 0 AND byte_count > 0",
        "manifest_checksum_valid": "checksum_sha256 RLIKE '^[a-f0-9]{64}$'",
        "manifest_not_rescued": "rescued_data IS NULL",
    }
)
def bronze_market_manifests():
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821 - injected by Databricks SDP
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("cloudFiles.includeExistingFiles", "true")
        .option("rescuedDataColumn", "_rescued_data")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "manifest.json")
        .schema(MARKET_MANIFEST_SCHEMA)
        .load(raw_market_path(spark))  # noqa: F821 - injected by Databricks SDP
        .select(
            "version",
            "source",
            "dataset",
            F.to_date("trading_date").alias("trading_date"),
            "endpoint",
            "adjusted",
            "include_otc",
            "request_id",
            "correlation_id",
            "status_code",
            "row_count",
            "byte_count",
            "checksum_sha256",
            "elapsed_ms",
            F.to_timestamp("landed_at").alias("landed_at"),
            "response_path",
            F.col("_metadata.file_path").alias("manifest_path"),
            F.current_timestamp().alias("ingested_at"),
            F.col("_rescued_data").alias("rescued_data"),
        )
    )
