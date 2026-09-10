"""Incrementally explode Massive news responses while retaining every ticker."""

from _article_pipeline_common import ARTICLE_RESPONSE_SCHEMA, raw_article_path
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(
    name="bronze_research_articles",
    comment="Raw Massive news articles with query, response, payload, and multi-ticker lineage.",
    cluster_by=["published_at"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "article_id_present": "article_id IS NOT NULL",
        "title_present": "title IS NOT NULL",
        "source_path_present": "source_path IS NOT NULL",
    }
)
def bronze_research_articles():
    responses = (
        spark.readStream.format("cloudFiles")  # noqa: F821 - injected by Databricks SDP
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("cloudFiles.includeExistingFiles", "true")
        .option("rescuedDataColumn", "_rescued_data")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "response.json")
        .schema(ARTICLE_RESPONSE_SCHEMA)
        .load(raw_article_path(spark))  # noqa: F821 - injected by Databricks SDP
    )
    return (
        responses.withColumn("source_path", F.col("_metadata.file_path"))
        .withColumn("query_ticker", F.regexp_extract("source_path", r"query_ticker=([^/]+)", 1))
        .withColumn("article", F.explode("results"))
        .select(
            F.col("article.id").alias("article_id"),
            F.col("article.title").alias("title"),
            F.col("article.author").alias("author"),
            F.col("article.publisher.name").alias("publisher_name"),
            F.col("article.publisher.homepage_url").alias("publisher_homepage_url"),
            F.to_timestamp("article.published_utc").alias("published_at"),
            F.col("article.article_url").alias("article_url"),
            F.col("article.tickers").alias("tickers"),
            F.col("article.image_url").alias("image_url"),
            F.col("article.description").alias("description"),
            F.col("article.keywords").alias("keywords"),
            "query_ticker",
            F.col("request_id").alias("source_request_id"),
            "source_path",
            F.to_json("article").alias("raw_record_json"),
            F.current_timestamp().alias("ingested_at"),
            F.col("_rescued_data").alias("rescued_data"),
        )
    )
