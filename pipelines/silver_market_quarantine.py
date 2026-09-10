"""Preserve every invalid or duplicate Bronze bar with its rejection reason."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_market_quarantine",
    comment="Rejected market bars retained for quality diagnostics and replay.",
    cluster_by=["trading_date", "quarantine_reason"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_or_fail("quarantine_reason_present", "quarantine_reason IS NOT NULL")
def silver_market_quarantine():
    return (
        spark.read.table("market_bars_classified")  # noqa: F821 - injected by Databricks SDP
        .filter(F.col("quality_reason").isNotNull() | (F.col("dedupe_rank") > 1))
        .withColumn(
            "quarantine_reason",
            F.coalesce(F.col("quality_reason"), F.lit("duplicate_ticker_date")),
        )
        .select(
            "record_id",
            F.col("ticker_raw").alias("ticker"),
            "trading_date",
            "event_timestamp",
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
            "transactions",
            "otc",
            "source_request_id",
            "source_path",
            "ingested_at",
            "raw_record_json",
            "rescued_data",
            "dedupe_rank",
            "quarantine_reason",
        )
    )
