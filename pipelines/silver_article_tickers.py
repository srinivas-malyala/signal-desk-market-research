"""Publish the many-to-many relationship between articles and mentioned tickers."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_article_tickers",
    comment="Distinct article/ticker relationships; an article may mention multiple securities.",
    cluster_by=["ticker", "article_id"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "article_id_present": "article_id IS NOT NULL",
        "valid_ticker": "ticker RLIKE '^[A-Z][A-Z0-9.-]{0,9}$'",
    }
)
def silver_article_tickers():
    return (
        spark.read.table("bronze_research_articles")  # noqa: F821 - injected by Databricks SDP
        .select("article_id", F.explode("tickers").alias("ticker"))
        .select("article_id", F.upper(F.trim("ticker")).alias("ticker"))
        .filter(F.col("ticker").rlike(r"^[A-Z][A-Z0-9.-]{0,9}$"))
        .dropDuplicates(["article_id", "ticker"])
    )
