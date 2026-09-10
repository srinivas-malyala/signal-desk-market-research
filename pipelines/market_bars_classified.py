"""Classify every Bronze bar and assign a deterministic duplicate rank."""

from _market_pipeline_common import MARKET_QUALITY_RULES
from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.temporary_view(
    name="market_bars_classified",
    comment="Pipeline-private quality classification shared by Silver accepted and quarantine datasets.",
)
def market_bars_classified():
    bronze = spark.read.table("bronze_market_daily")  # noqa: F821 - injected by Databricks SDP
    quality_reason = F.lit(None).cast("string")
    for reason, condition in reversed(MARKET_QUALITY_RULES):
        quality_reason = F.when(F.expr(condition), F.lit(reason)).otherwise(quality_reason)

    classified = bronze.withColumn("quality_reason", quality_reason).withColumn(
        "record_id",
        F.sha2(
            F.concat_ws(
                "||",
                F.coalesce(F.col("source_path"), F.lit("")),
                F.coalesce(F.col("ticker_raw"), F.lit("")),
                F.coalesce(F.col("raw_record_json"), F.lit("")),
            ),
            256,
        ),
    )
    preferred_record = Window.partitionBy("ticker_raw", "trading_date").orderBy(
        F.when(F.col("quality_reason").isNull(), F.lit(0)).otherwise(F.lit(1)),
        F.col("ingested_at").desc(),
        F.col("source_path").desc(),
        F.col("record_id").desc(),
    )
    return classified.withColumn("dedupe_rank", F.row_number().over(preferred_record))
