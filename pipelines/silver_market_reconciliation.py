"""Assert that accepted and quarantined Silver rows exactly cover Bronze."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_market_reconciliation",
    comment="Pipeline-wide row conservation and Silver uniqueness evidence.",
)
@dp.expect_all_or_fail(
    {
        "all_bronze_rows_accounted_for": "bronze_rows = silver_rows + quarantine_rows",
        "silver_key_unique": "duplicate_silver_keys = 0",
    }
)
def silver_market_reconciliation():
    bronze = spark.read.table("bronze_market_daily")  # noqa: F821 - injected by Databricks SDP
    silver = spark.read.table("silver_market_bars")  # noqa: F821 - injected by Databricks SDP
    quarantine = spark.read.table("silver_market_quarantine")  # noqa: F821 - injected by Databricks SDP
    duplicate_keys = (
        silver.groupBy("ticker", "trading_date")
        .count()
        .filter(F.col("count") > 1)
        .agg(F.count("*").alias("duplicate_silver_keys"))
    )
    counts = (
        bronze.agg(F.count("*").alias("bronze_rows"))
        .crossJoin(silver.agg(F.count("*").alias("silver_rows")))
        .crossJoin(quarantine.agg(F.count("*").alias("quarantine_rows")))
        .crossJoin(duplicate_keys)
    )
    return counts.withColumn("checked_at", F.current_timestamp())
