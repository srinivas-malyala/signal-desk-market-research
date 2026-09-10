"""Incrementally explode immutable Massive grouped-daily responses into Bronze."""

from _market_pipeline_common import MARKET_RESPONSE_SCHEMA, raw_market_path
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(
    name="bronze_market_daily",
    comment="Append-only Massive grouped daily bars with immutable source lineage.",
    cluster_by=["trading_date", "ticker_raw"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "source_file_present": "source_path IS NOT NULL",
        "partition_date_present": "trading_date IS NOT NULL",
        "raw_record_present": "raw_record_json IS NOT NULL",
    }
)
@dp.expect_all(
    {
        "ticker_observed": "ticker_raw IS NOT NULL",
        "event_timestamp_observed": "event_timestamp IS NOT NULL",
        "request_id_observed": "source_request_id IS NOT NULL",
    }
)
def bronze_market_daily():
    responses = (
        spark.readStream.format("cloudFiles")  # noqa: F821 - injected by Databricks SDP
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("cloudFiles.includeExistingFiles", "true")
        .option("rescuedDataColumn", "_rescued_data")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "response.json")
        .schema(MARKET_RESPONSE_SCHEMA)
        .load(raw_market_path(spark))  # noqa: F821 - injected by Databricks SDP
    )

    return (
        responses.withColumn("source_path", F.col("_metadata.file_path"))
        .withColumn(
            "trading_date",
            F.to_date(F.regexp_extract("source_path", r"trading_date=(\d{4}-\d{2}-\d{2})", 1)),
        )
        .withColumn("bar", F.explode("results"))
        .select(
            F.upper(F.trim(F.col("bar.T"))).alias("ticker_raw"),
            "trading_date",
            F.expr("timestamp_millis(bar.t)").alias("event_timestamp"),
            F.col("bar.o").cast("double").alias("open"),
            F.col("bar.h").cast("double").alias("high"),
            F.col("bar.l").cast("double").alias("low"),
            F.col("bar.c").cast("double").alias("close"),
            F.col("bar.vw").cast("double").alias("vwap"),
            F.col("bar.v").cast("double").alias("volume"),
            F.col("bar.n").cast("long").alias("transactions"),
            F.coalesce(F.col("bar.otc"), F.lit(False)).alias("otc"),
            F.col("request_id").alias("source_request_id"),
            "source_path",
            F.current_timestamp().alias("ingested_at"),
            F.to_json("bar").alias("raw_record_json"),
            F.col("_rescued_data").alias("rescued_data"),
        )
    )
