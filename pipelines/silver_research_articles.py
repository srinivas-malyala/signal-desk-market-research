"""Publish one deterministic record per research article."""

from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_research_articles",
    comment="Unique Massive articles with publisher, publication time, URL, and freshness.",
    cluster_by=["published_at", "article_id"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "article_id_present": "article_id IS NOT NULL",
        "title_present": "title IS NOT NULL",
        "valid_article_url": "article_url IS NULL OR article_url RLIKE '^https?://'",
    }
)
def silver_research_articles():
    bronze = spark.read.table("bronze_research_articles")  # noqa: F821 - injected by Databricks SDP
    latest = Window.partitionBy("article_id").orderBy(
        F.col("published_at").desc_nulls_last(), F.col("ingested_at").desc(), F.col("source_path").desc()
    )
    return (
        bronze.withColumn("article_rank", F.row_number().over(latest))
        .filter(F.col("article_rank") == 1)
        .select(
            "article_id",
            "title",
            "author",
            "publisher_name",
            "publisher_homepage_url",
            "published_at",
            "article_url",
            "image_url",
            "description",
            "keywords",
            "source_request_id",
            "source_path",
            "ingested_at",
        )
    )
