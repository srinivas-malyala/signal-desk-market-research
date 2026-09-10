"""Assert uniqueness and company referential integrity across structured SEC tables."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="sec_structured_reconciliation",
    comment="Single-row integrity evidence for SEC companies, filings, and Company Facts.",
)
@dp.expect_all_or_fail(
    {
        "company_ciks_resolve": "orphan_filing_ciks = 0 AND orphan_fact_ciks = 0",
        "accessions_unique": "duplicate_accessions = 0",
        "fact_keys_unique": "duplicate_fact_keys = 0",
    }
)
def sec_structured_reconciliation():
    companies = spark.read.table("silver_sec_companies")  # noqa: F821 - injected by Databricks SDP
    filings = spark.read.table("silver_sec_filings")  # noqa: F821 - injected by Databricks SDP
    facts = spark.read.table("silver_sec_facts")  # noqa: F821 - injected by Databricks SDP
    company_ciks = companies.select("cik").distinct()
    orphan_filings = filings.select("cik").distinct().join(company_ciks, "cik", "left_anti")
    orphan_facts = facts.select("cik").distinct().join(company_ciks, "cik", "left_anti")
    duplicate_accessions = filings.groupBy("accession_number").count().filter(F.col("count") > 1)
    duplicate_facts = (
        facts.groupBy(
            "cik",
            "taxonomy",
            "concept",
            "unit",
            "accession_number",
            "period_start",
            "period_end",
            "frame",
        )
        .count()
        .filter(F.col("count") > 1)
    )
    return (
        companies.agg(F.countDistinct("cik").alias("company_count"))
        .crossJoin(filings.agg(F.count("*").alias("filing_count")))
        .crossJoin(facts.agg(F.count("*").alias("fact_count")))
        .crossJoin(orphan_filings.agg(F.count("*").alias("orphan_filing_ciks")))
        .crossJoin(orphan_facts.agg(F.count("*").alias("orphan_fact_ciks")))
        .crossJoin(duplicate_accessions.agg(F.count("*").alias("duplicate_accessions")))
        .crossJoin(duplicate_facts.agg(F.count("*").alias("duplicate_fact_keys")))
        .withColumn("checked_at", F.current_timestamp())
    )
