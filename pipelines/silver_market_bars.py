"""Publish valid, deterministic ticker-day bars for downstream analytics."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_market_bars",
    comment="Validated and deduplicated U.S. stock daily bars from Massive.",
    cluster_by=["trading_date", "ticker"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "unique_candidate": "dedupe_rank = 1",
        "quality_accepted": "quality_reason IS NULL",
        "ticker_present": "ticker IS NOT NULL",
        "ohlc_consistent": "high >= greatest(open, close, low) AND low <= least(open, close, high)",
        "volume_nonnegative": "volume >= 0",
    }
)
def silver_market_bars():
    return (
        spark.read.table("market_bars_classified")  # noqa: F821 - injected by Databricks SDP
        .filter(F.col("quality_reason").isNull() & (F.col("dedupe_rank") == 1))
        .select(
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
            "record_id",
            "dedupe_rank",
            "quality_reason",
        )
    )
