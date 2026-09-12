"""Publish daily active researcher counts from append-only agent events."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_daily_active_researchers",
    comment="Daily distinct pseudonymous researchers and agent invocation volume.",
    cluster_by=["activity_date"],
)
def gold_daily_active_researchers():
    activity = spark.read.table("silver_agent_activity").filter(  # noqa: F821
        (F.col("source_table") == "agent_tool_events")
        & (F.col("change_type") == "insert")
        & F.col("user_pseudonym").isNotNull()
    )
    return activity.groupBy("activity_date").agg(
        F.countDistinct("user_pseudonym").alias("daily_active_researchers"),
        F.count("*").alias("agent_invocations"),
        F.max("synced_at").alias("source_max_synced_at"),
        F.max("source_latency_seconds").alias("max_source_latency_seconds"),
        F.current_timestamp().alias("metric_refreshed_at"),
        F.lit("silver_agent_activity:agent_tool_events").alias("metric_source"),
    )
