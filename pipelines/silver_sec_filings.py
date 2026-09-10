"""Publish unique selected SEC filing metadata from immutable manifests."""

from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_sec_filings",
    comment="Selected 10-K, 10-Q, and 8-K filing metadata with exact SEC document provenance.",
    cluster_by=["ticker", "filing_date"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "valid_accession": "accession_number RLIKE '^[0-9]{10}-[0-9]{2}-[0-9]{6}$'",
        "valid_cik": "cik RLIKE '^[0-9]{10}$'",
        "selected_form": "regexp_replace(form, '/A$', '') IN ('10-K', '10-Q', '8-K')",
        "filing_date_present": "filing_date IS NOT NULL",
        "official_source_url": "source_url RLIKE '^https://www[.]sec[.]gov/Archives/edgar/data/'",
    }
)
def silver_sec_filings():
    manifests = spark.read.table("bronze_sec_manifests").filter(F.col("kind") == "filing")  # noqa: F821
    latest = Window.partitionBy("accession_number").orderBy(
        F.col("fetched_at").desc(), F.col("checksum_sha256").desc()
    )
    return (
        manifests.withColumn("accession_rank", F.row_number().over(latest))
        .filter(F.col("accession_rank") == 1)
        .select(
            "accession_number",
            "cik",
            "ticker",
            "form",
            F.regexp_replace("form", "/A$", "").alias("base_form"),
            "filing_date",
            "report_date",
            "acceptance_datetime",
            "primary_document",
            F.col("primary_doc_description").alias("title"),
            "source_url",
            "content_type",
            "byte_count",
            "checksum_sha256",
            "fetched_at",
            "landing_path",
        )
    )
