"""Publish the latest SEC company and ticker reference mapping."""

from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_sec_companies",
    comment="Latest SEC company identity, ticker, exchange, SIC industry, and fiscal-year attributes.",
    cluster_by=["ticker", "cik"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "valid_cik": "cik RLIKE '^[0-9]{10}$'",
        "valid_ticker": "ticker RLIKE '^[A-Z][A-Z0-9.-]{0,9}$'",
        "company_name_present": "company_name IS NOT NULL",
        "official_source_url": "source_url RLIKE '^https://data[.]sec[.]gov/'",
    }
)
def silver_sec_companies():
    submissions = spark.read.table("bronze_sec_submissions")  # noqa: F821 - injected by Databricks SDP
    manifests = (
        spark.read.table("bronze_sec_manifests")  # noqa: F821 - injected by Databricks SDP
        .filter(F.col("kind") == "submissions")
        .select(
            "landing_path",
            "source_url",
            "fetched_at",
            F.col("cik").alias("manifest_cik"),
            F.col("checksum_sha256").alias("manifest_checksum"),
        )
    )
    latest = Window.partitionBy("cik").orderBy(F.col("fetched_at").desc(), F.col("checksum_sha256").desc())
    current = (
        submissions.join(
            manifests,
            (submissions.checksum_sha256 == manifests.manifest_checksum)
            & (submissions.cik == manifests.manifest_cik),
        )
        .withColumn("snapshot_rank", F.row_number().over(latest))
        .filter(F.col("snapshot_rank") == 1)
    )
    return (
        current.select("*", F.posexplode("tickers").alias("ticker_index", "ticker"))
        .select(
            "cik",
            F.upper("ticker").alias("ticker"),
            F.element_at("exchanges", F.col("ticker_index") + 1).alias("exchange"),
            "company_name",
            "entity_type",
            "sic",
            F.col("sic_description").alias("industry"),
            "description",
            "website",
            "investor_website",
            "category",
            "fiscal_year_end",
            "state_of_incorporation",
            "source_url",
            "fetched_at",
            F.col("checksum_sha256").alias("checksum_sha256"),
        )
    )
