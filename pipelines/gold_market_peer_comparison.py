"""Compare each ticker's daily return with the available broad market peer set."""

from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_market_peer_comparison",
    comment="Ticker-day return percentile and relative return versus all covered U.S. equities.",
    cluster_by=["trading_date", "ticker"],
)
@dp.expect_all_or_fail(
    {
        "peer_count_positive": "peer_count > 0",
        "percentile_bounded": "return_percentile BETWEEN 0 AND 1",
    }
)
def gold_market_peer_comparison():
    performance = (
        spark.read.table("gold_stock_performance")  # noqa: F821 - injected by Databricks SDP
        .filter(F.col("daily_return").isNotNull())
    )
    market_day = performance.groupBy("trading_date").agg(
        F.count("*").alias("peer_count"),
        F.avg("daily_return").alias("market_average_return"),
        F.expr("percentile_approx(daily_return, 0.5, 10000)").alias("market_median_return"),
        F.stddev_samp("daily_return").alias("market_return_stddev"),
    )
    percentile_window = Window.partitionBy("trading_date").orderBy(F.col("daily_return"))
    ranked = performance.withColumn("return_percentile", F.percent_rank().over(percentile_window))
    return (
        ranked.join(market_day, "trading_date")
        .withColumn("relative_return", F.col("daily_return") - F.col("market_average_return"))
        .select(
            "ticker",
            "trading_date",
            "daily_return",
            "market_average_return",
            "market_median_return",
            "market_return_stddev",
            "relative_return",
            "return_percentile",
            "peer_count",
            "otc",
        )
    )
