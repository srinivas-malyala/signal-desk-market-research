"""Publish daily per-tool usage, outcome, and latency metrics."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_tool_usage_latency",
    comment="Daily tool invocation volume, outcomes, and latency percentiles.",
    cluster_by=["activity_date", "tool_name"],
)
def gold_tool_usage_latency():
    activity = spark.read.table("silver_agent_activity").filter(  # noqa: F821
        (F.col("source_table") == "agent_tool_events") & (F.col("change_type") == "insert")
    )
    return activity.groupBy("activity_date", "tool_name").agg(
        F.count("*").alias("invocation_count"),
        F.sum(F.when(F.col("status") == "success", 1).otherwise(0)).alias("success_count"),
        F.sum(F.when(F.col("status") == "error", 1).otherwise(0)).alias("error_count"),
        F.sum(F.when(F.col("duration_ms").isNull(), 1).otherwise(0)).alias("null_duration_count"),
        F.avg("duration_ms").alias("average_duration_ms"),
        F.percentile_approx("duration_ms", 0.5, 10000).alias("p50_duration_ms"),
        F.percentile_approx("duration_ms", 0.95, 10000).alias("p95_duration_ms"),
        F.max("synced_at").alias("source_max_synced_at"),
        F.current_timestamp().alias("metric_refreshed_at"),
        F.lit("silver_agent_activity:agent_tool_events").alias("metric_source"),
    )
