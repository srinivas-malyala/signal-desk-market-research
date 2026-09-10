"""Reconcile each landed manifest to the exact number of Bronze bars."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="market_ingestion_reconciliation",
    comment="Per-date manifest-to-Bronze completeness evidence; every row must report MATCH.",
    cluster_by=["trading_date"],
)
@dp.expect_or_fail("manifest_matches_bronze", "reconciliation_status = 'MATCH'")
def market_ingestion_reconciliation():
    manifests = (
        spark.read.table("bronze_market_manifests")  # noqa: F821 - injected by Databricks SDP
        .groupBy("trading_date")
        .agg(
            F.count("*").alias("manifest_count"),
            F.sum("row_count").alias("manifest_row_count"),
            F.max("landed_at").alias("landed_at"),
        )
    )
    bronze = spark.read.table("bronze_market_daily").groupBy("trading_date").agg(  # noqa: F821
        F.count("*").alias("bronze_row_count")
    )
    return (
        manifests.join(bronze, "trading_date", "full")
        .fillna(0, subset=["manifest_count", "manifest_row_count", "bronze_row_count"])
        .withColumn(
            "reconciliation_status",
            F.when(
                (F.col("manifest_count") == 1)
                & (F.col("manifest_row_count") == F.col("bronze_row_count")),
                F.lit("MATCH"),
            ).otherwise(F.lit("MISMATCH")),
        )
        .withColumn("checked_at", F.current_timestamp())
    )
