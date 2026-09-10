"""Minimal Lakeflow dataset used only to prove Phase 0 pipeline capability."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="phase0_capability_check",
    comment="One-row capability gate; replaced by Bronze/Silver/Gold datasets in Phase 2.",
)
def phase0_capability_check():
    return spark.range(1).select(
        F.lit("signal-desk").alias("project"),
        F.current_timestamp().alias("validated_at"),
    )
