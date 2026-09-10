"""Schemas and paths for content-addressed Massive research articles."""

from pyspark.sql import types as T

ARTICLE_SCHEMA = T.StructType(
    [
        T.StructField("id", T.StringType()),
        T.StructField(
            "publisher",
            T.StructType(
                [
                    T.StructField("name", T.StringType()),
                    T.StructField("homepage_url", T.StringType()),
                    T.StructField("logo_url", T.StringType()),
                    T.StructField("favicon_url", T.StringType()),
                ]
            ),
        ),
        T.StructField("title", T.StringType()),
        T.StructField("author", T.StringType()),
        T.StructField("published_utc", T.StringType()),
        T.StructField("article_url", T.StringType()),
        T.StructField("tickers", T.ArrayType(T.StringType())),
        T.StructField("image_url", T.StringType()),
        T.StructField("description", T.StringType()),
        T.StructField("keywords", T.ArrayType(T.StringType())),
    ]
)

ARTICLE_RESPONSE_SCHEMA = T.StructType(
    [
        T.StructField("request_id", T.StringType()),
        T.StructField("results", T.ArrayType(ARTICLE_SCHEMA)),
        T.StructField("status", T.StringType()),
        T.StructField("count", T.LongType()),
        T.StructField("next_url", T.StringType()),
        T.StructField("_rescued_data", T.StringType()),
    ]
)


def raw_article_path(spark) -> str:
    return f"{spark.conf.get('signal_desk.raw_volume_path').rstrip('/')}/research_articles"
