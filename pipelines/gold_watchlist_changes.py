"""Publish daily watchlist change metrics."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_watchlist_changes",
    comment="Daily watchlist creates, updates, and deletes from Lakebase CDC.",
    cluster_by=["activity_date", "action_type"],
)
def gold_watchlist_changes():
    activity = spark.read.table("silver_agent_activity").filter(  # noqa: F821
        F.col("source_table") == "watchlist_tickers"
    )
    return activity.groupBy("activity_date", "action_type").agg(
        F.count("*").alias("change_count"),
        F.max("synced_at").alias("source_max_synced_at"),
        F.max("source_latency_seconds").alias("max_source_latency_seconds"),
        F.current_timestamp().alias("metric_refreshed_at"),
        F.lit("silver_agent_activity:watchlist_tickers").alias("metric_source"),
    )
