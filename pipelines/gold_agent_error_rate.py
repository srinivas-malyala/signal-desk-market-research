"""Publish daily aggregate agent error rates."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_agent_error_rate",
    comment="Daily agent invocation error rate across all tools.",
    cluster_by=["activity_date"],
)
def gold_agent_error_rate():
    activity = spark.read.table("silver_agent_activity").filter(  # noqa: F821
        (F.col("source_table") == "agent_tool_events") & (F.col("change_type") == "insert")
    )
    return activity.groupBy("activity_date").agg(
        F.count("*").alias("invocation_count"),
        F.sum(F.when(F.col("status") == "error", 1).otherwise(0)).alias("error_count"),
        F.avg(F.when(F.col("status") == "error", F.lit(1.0)).otherwise(F.lit(0.0))).alias("error_rate"),
        F.max("synced_at").alias("source_max_synced_at"),
        F.current_timestamp().alias("metric_refreshed_at"),
        F.lit("silver_agent_activity:agent_tool_events").alias("metric_source"),
    )
