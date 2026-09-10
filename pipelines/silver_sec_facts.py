"""Normalize dynamic XBRL taxonomies, concepts, units, and observations."""

from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_sec_facts",
    comment="Deduplicated SEC XBRL observations retaining taxonomy, unit, fiscal period, and accession.",
    cluster_by=["cik", "concept", "period_end"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "valid_cik": "cik RLIKE '^[0-9]{10}$'",
        "taxonomy_present": "taxonomy IS NOT NULL",
        "concept_present": "concept IS NOT NULL",
        "unit_present": "unit IS NOT NULL",
        "period_end_present": "period_end IS NOT NULL",
        "filed_date_present": "filed_date IS NOT NULL",
    }
)
def silver_sec_facts():
    snapshots = spark.read.table("bronze_sec_company_facts")  # noqa: F821 - injected by Databricks SDP
    manifests = (
        spark.read.table("bronze_sec_manifests")  # noqa: F821 - injected by Databricks SDP
        .filter(F.col("kind") == "companyfacts")
        .select(
            "landing_path",
            "source_url",
            "fetched_at",
            F.col("cik").alias("manifest_cik"),
            F.col("checksum_sha256").alias("manifest_checksum"),
        )
    )
    expanded = (
        snapshots.join(
            manifests,
            (snapshots.checksum_sha256 == manifests.manifest_checksum)
            & (snapshots.cik == manifests.manifest_cik),
        )
        .select("*", F.explode(F.map_entries("facts")).alias("taxonomy_entry"))
        .select("*", F.explode(F.map_entries("taxonomy_entry.value")).alias("concept_entry"))
        .select("*", F.explode(F.map_entries("concept_entry.value.units")).alias("unit_entry"))
        .select("*", F.explode("unit_entry.value").alias("observation"))
        .select(
            "cik",
            "entity_name",
            F.col("taxonomy_entry.key").alias("taxonomy"),
            F.col("concept_entry.key").alias("concept"),
            F.col("concept_entry.value.label").alias("label"),
            F.col("concept_entry.value.description").alias("description"),
            F.col("unit_entry.key").alias("unit"),
            F.to_date("observation.start").alias("period_start"),
            F.to_date("observation.end").alias("period_end"),
            F.col("observation.val").alias("value_text"),
            F.col("observation.val").cast("decimal(38,8)").alias("value_decimal"),
            F.col("observation.accn").alias("accession_number"),
            F.col("observation.fy").alias("fiscal_year"),
            F.col("observation.fp").alias("fiscal_period"),
            F.col("observation.form").alias("form"),
            F.to_date("observation.filed").alias("filed_date"),
            F.col("observation.frame").alias("frame"),
            "source_url",
            "fetched_at",
            "checksum_sha256",
        )
    )
    fact_key = Window.partitionBy(
        "cik",
        "taxonomy",
        "concept",
        "unit",
        "accession_number",
        "period_start",
        "period_end",
        "frame",
    ).orderBy(
        F.col("fetched_at").desc(),
        F.col("checksum_sha256").desc(),
        F.col("value_text").desc(),
    )
    return expanded.withColumn("fact_rank", F.row_number().over(fact_key)).filter(F.col("fact_rank") == 1).drop(
        "fact_rank"
    )
