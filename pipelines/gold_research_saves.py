"""Publish daily research-note and analysis-report change metrics."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_research_saves",
    comment="Daily research note and analysis report actions without authored content.",
    cluster_by=["activity_date", "research_type", "action_type"],
)
def gold_research_saves():
    activity = spark.read.table("silver_agent_activity").filter(  # noqa: F821
        F.col("source_table").isin("research_notes", "analysis_reports")
    )
    return (
        activity.withColumn(
            "research_type",
            F.when(F.col("source_table") == "research_notes", F.lit("note")).otherwise(F.lit("report")),
        )
        .groupBy("activity_date", "research_type", "action_type")
        .agg(
            F.count("*").alias("change_count"),
            F.countDistinct("user_pseudonym").alias("researcher_count"),
            F.max("synced_at").alias("source_max_synced_at"),
            F.max("source_latency_seconds").alias("max_source_latency_seconds"),
            F.current_timestamp().alias("metric_refreshed_at"),
            F.lit("silver_agent_activity:research_notes,analysis_reports").alias("metric_source"),
        )
    )
