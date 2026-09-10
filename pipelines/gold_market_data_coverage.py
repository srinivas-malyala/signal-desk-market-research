"""Publish per-date coverage and data-quality metrics for operations and analytics."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_market_data_coverage",
    comment="Per-trading-date ingestion completeness, Silver acceptance, and quarantine metrics.",
    cluster_by=["trading_date"],
)
def gold_market_data_coverage():
    manifests = spark.read.table("bronze_market_manifests").select(  # noqa: F821
        "trading_date",
        F.col("row_count").alias("manifest_rows"),
        "byte_count",
        "elapsed_ms",
        "landed_at",
    )
    bronze = (
        spark.read.table("bronze_market_daily")  # noqa: F821 - injected by Databricks SDP
        .groupBy("trading_date")
        .agg(F.count("*").alias("bronze_rows"), F.countDistinct("ticker_raw").alias("bronze_tickers"))
    )
    silver = (
        spark.read.table("silver_market_bars")  # noqa: F821 - injected by Databricks SDP
        .groupBy("trading_date")
        .agg(F.count("*").alias("silver_rows"), F.countDistinct("ticker").alias("silver_tickers"))
    )
    quarantine = (
        spark.read.table("silver_market_quarantine")  # noqa: F821 - injected by Databricks SDP
        .groupBy("trading_date")
        .agg(F.count("*").alias("quarantine_rows"))
    )
    return (
        manifests.join(bronze, "trading_date", "full")
        .join(silver, "trading_date", "full")
        .join(quarantine, "trading_date", "full")
        .fillna(
            0,
            subset=[
                "manifest_rows",
                "bronze_rows",
                "bronze_tickers",
                "silver_rows",
                "silver_tickers",
                "quarantine_rows",
            ],
        )
        .withColumn(
            "coverage_status",
            F.when(
                (F.col("manifest_rows") == F.col("bronze_rows"))
                & (F.col("bronze_rows") == F.col("silver_rows") + F.col("quarantine_rows")),
                F.lit("COMPLETE"),
            ).otherwise(F.lit("INCOMPLETE")),
        )
        .withColumn(
            "acceptance_rate",
            F.when(F.col("bronze_rows") > 0, F.col("silver_rows") / F.col("bronze_rows")),
        )
        .withColumn("checked_at", F.current_timestamp())
    )
