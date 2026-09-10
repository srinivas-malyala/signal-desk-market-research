"""Compare ticker returns with peers in the SEC SIC industry mapping."""

from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_industry_peer_comparison",
    comment="Ticker-day performance relative to companies sharing the SEC SIC industry.",
    cluster_by=["industry", "trading_date"],
)
@dp.expect_all_or_fail(
    {
        "industry_present": "industry IS NOT NULL",
        "industry_peer_count_positive": "industry_peer_count > 0",
        "industry_percentile_bounded": "industry_return_percentile BETWEEN 0 AND 1",
    }
)
def gold_industry_peer_comparison():
    performance = (
        spark.read.table("gold_stock_performance")  # noqa: F821 - injected by Databricks SDP
        .filter(F.col("daily_return").isNotNull())
    )
    company_rank = Window.partitionBy("ticker").orderBy(F.col("fetched_at").desc(), F.col("cik"))
    companies = (
        spark.read.table("silver_sec_companies")  # noqa: F821 - injected by Databricks SDP
        .withColumn("ticker_rank", F.row_number().over(company_rank))
        .filter(F.col("ticker_rank") == 1)
        .select("ticker", "cik", "company_name", "sic", "industry")
    )
    enriched = performance.join(companies, "ticker").filter(F.col("industry").isNotNull())
    industry_day = enriched.groupBy("industry", "trading_date").agg(
        F.count("*").alias("industry_peer_count"),
        F.avg("daily_return").alias("industry_average_return"),
        F.expr("percentile_approx(daily_return, 0.5, 10000)").alias("industry_median_return"),
    )
    ranking = Window.partitionBy("industry", "trading_date").orderBy("daily_return")
    return (
        enriched.withColumn("industry_return_percentile", F.percent_rank().over(ranking))
        .join(industry_day, ["industry", "trading_date"])
        .withColumn("relative_industry_return", F.col("daily_return") - F.col("industry_average_return"))
        .select(
            "ticker",
            "cik",
            "company_name",
            "sic",
            "industry",
            "trading_date",
            "daily_return",
            "industry_average_return",
            "industry_median_return",
            "relative_industry_return",
            "industry_return_percentile",
            "industry_peer_count",
        )
    )
