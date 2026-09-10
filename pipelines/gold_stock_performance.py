"""Build ticker-day return, volatility, price-range, and volume metrics."""

from math import sqrt

from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_stock_performance",
    comment="Ticker-day performance with reproducible trailing 20-session analytics.",
    cluster_by=["ticker", "trading_date"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "ticker_present": "ticker IS NOT NULL",
        "trading_date_present": "trading_date IS NOT NULL",
        "window_observations_bounded": "window_observations BETWEEN 1 AND 20",
    }
)
def gold_stock_performance():
    silver = spark.read.table("silver_market_bars")  # noqa: F821 - injected by Databricks SDP
    ticker_history = Window.partitionBy("ticker").orderBy("trading_date")
    trailing_20 = ticker_history.rowsBetween(-19, 0)

    daily = (
        silver.withColumn("previous_close", F.lag("close").over(ticker_history))
        .withColumn("previous_volume", F.lag("volume").over(ticker_history))
        .withColumn(
            "daily_return",
            F.when(F.col("previous_close") > 0, F.col("close") / F.col("previous_close") - F.lit(1.0)),
        )
        .withColumn(
            "volume_change",
            F.when(F.col("previous_volume") > 0, F.col("volume") / F.col("previous_volume") - F.lit(1.0)),
        )
    )
    with_windows = (
        daily.withColumn("window_observations", F.count("close").over(trailing_20))
        .withColumn("annualized_volatility_raw", F.stddev_samp("daily_return").over(trailing_20) * F.lit(sqrt(252)))
        .withColumn("average_volume_raw", F.avg("volume").over(trailing_20))
        .withColumn("high_raw", F.max("high").over(trailing_20))
        .withColumn("low_raw", F.min("low").over(trailing_20))
    )
    full_window = F.col("window_observations") == 20
    return (
        with_windows.withColumn(
            "annualized_volatility_20d",
            F.when(full_window, F.col("annualized_volatility_raw")),
        )
        .withColumn("average_volume_20d", F.when(full_window, F.col("average_volume_raw")))
        .withColumn("high_20d", F.when(full_window, F.col("high_raw")))
        .withColumn("low_20d", F.when(full_window, F.col("low_raw")))
        .select(
            "ticker",
            "trading_date",
            "close",
            "volume",
            "daily_return",
            "volume_change",
            "annualized_volatility_20d",
            "average_volume_20d",
            "high_20d",
            "low_20d",
            "window_observations",
            "otc",
            "source_request_id",
        )
    )
